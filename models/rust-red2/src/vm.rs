use std::collections::BTreeMap;
use std::io::{ErrorKind, Read, Write};
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::bytecode::{Data, Instruction, Opcode, Program, ProgramBundle, Red2Error};

#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Int(i64),
    Float(f64),
    Char(String),
    Symbol(String),
    Var(usize, Option<String>),
    Lambda(Vec<String>, Box<Expr>),
    App(Vec<Expr>),
    Pair(Box<Expr>, Box<Expr>),
    Closure(Box<Expr>, Vec<Expr>),
}

impl Expr {
    pub fn to_source(&self) -> String {
        match self {
            Expr::Int(value) => value.to_string(),
            Expr::Float(value) => value.to_string(),
            Expr::Char(value) => format!("#\\{value}"),
            Expr::Symbol(value) => value.clone(),
            Expr::Pair(car, cdr) => {
                format!("(CONS {} {})", car.to_source(), cdr.to_source())
            }
            Expr::Var(_, Some(name)) => name.clone(),
            Expr::Var(index, None) => format!("(VAR {index})"),
            Expr::Lambda(params, body) => {
                format!("(LAMBDA ({}) {})", params.join(" "), body.to_source())
            }
            Expr::Closure(expr, _) => expr.to_source(),
            Expr::App(items) => {
                let inner = items
                    .iter()
                    .map(Expr::to_source)
                    .collect::<Vec<_>>()
                    .join(" ");
                format!("({inner})")
            }
        }
    }
}

pub trait ClockSource {
    fn now_ms(&mut self) -> i64;
}

pub struct SystemClockSource;

impl ClockSource for SystemClockSource {
    fn now_ms(&mut self) -> i64 {
        match SystemTime::now().duration_since(UNIX_EPOCH) {
            Ok(duration) => duration.as_millis().min(i64::MAX as u128) as i64,
            Err(_) => 0,
        }
    }
}

pub struct LatestFileClockSource {
    path: PathBuf,
    latest: i64,
}

impl LatestFileClockSource {
    pub fn new(path: PathBuf, initial_ms: i64) -> Self {
        Self {
            path,
            latest: initial_ms,
        }
    }
}

impl ClockSource for LatestFileClockSource {
    fn now_ms(&mut self) -> i64 {
        let Ok(text) = std::fs::read_to_string(&self.path) else {
            return self.latest;
        };
        for line in text.lines() {
            if let Ok(value) = line.trim().parse::<i64>() {
                self.latest = value;
            }
        }
        self.latest
    }
}

pub fn run(program: &Program, quantum: u32) -> Result<Expr, Red2Error> {
    let mut parser = Parser { program };
    let expr = parser.parse(program.entry as usize)?;
    let mut reducer = Reducer {
        bundle: None,
        parsed_definitions: BTreeMap::new(),
        remaining: quantum,
        steps: 0,
    };
    reducer.reduce(expr, &[])
}

pub fn run_bundle(bundle: &ProgramBundle, quantum: u32) -> Result<Expr, Red2Error> {
    let expr = parse_bundle_entry(bundle)?;
    let mut reducer = Reducer {
        bundle: Some(bundle),
        parsed_definitions: BTreeMap::new(),
        remaining: quantum,
        steps: 0,
    };
    reducer.reduce(expr, &[])
}

pub fn parse_bundle_entry(bundle: &ProgramBundle) -> Result<Expr, Red2Error> {
    let program = bundle
        .entry()
        .ok_or_else(|| Red2Error("missing entry program".to_string()))?;
    let mut parser = Parser { program };
    parser.parse(program.entry as usize)
}

pub fn run_io_bundle<R: Read, W: Write>(
    bundle: &ProgramBundle,
    quantum: u32,
    input: &mut R,
    output: &mut W,
) -> Result<Expr, Red2Error> {
    let mut clock = SystemClockSource;
    run_io_bundle_with_clock(bundle, quantum, input, output, &mut clock)
}

pub fn run_io_bundle_with_clock<R: Read, W: Write, C: ClockSource>(
    bundle: &ProgramBundle,
    quantum: u32,
    input: &mut R,
    output: &mut W,
    clock: &mut C,
) -> Result<Expr, Red2Error> {
    let program = bundle
        .entry()
        .ok_or_else(|| Red2Error("missing entry program".to_string()))?;
    let mut parser = Parser { program };
    let expr = parser.parse(program.entry as usize)?;
    let reducer = Reducer {
        bundle: Some(bundle),
        parsed_definitions: BTreeMap::new(),
        remaining: quantum,
        steps: 0,
    };
    IoRunner {
        reducer,
        quantum,
        input,
        output,
        clock,
    }
    .run_action(expr, &[])
}

struct Parser<'a> {
    program: &'a Program,
}

impl Parser<'_> {
    fn parse(&mut self, pc: usize) -> Result<Expr, Red2Error> {
        let inst = self
            .program
            .instructions
            .get(pc)
            .ok_or_else(|| Red2Error(format!("instruction index out of range: {pc}")))?;
        match inst.opcode {
            Opcode::App => self.parse_app(pc),
            Opcode::Lambda => self.parse_lambda(pc),
            Opcode::Struct => self.parse_struct(pc),
            Opcode::Var => match &inst.data {
                Data::Int(index) => Ok(Expr::Var(*index as usize, None)),
                Data::String(name) => Ok(Expr::Var(0, Some(name.clone()))),
                _ => Err(Red2Error("VAR requires integer data".to_string())),
            },
            _ => instruction_expr(inst),
        }
    }

    fn parse_app(&mut self, pc: usize) -> Result<Expr, Red2Error> {
        let mut app_pcs = Vec::new();
        let mut operator_pc = pc;
        while let Some(inst) = self.program.instructions.get(operator_pc) {
            if inst.opcode != Opcode::App {
                break;
            }
            let Data::Int(arg_pc) = inst.data else {
                return Err(Red2Error("APP requires integer data".to_string()));
            };
            app_pcs.push(arg_pc as usize);
            operator_pc += 1;
        }
        let mut items = vec![self.parse(operator_pc)?];
        for arg_pc in app_pcs {
            items.push(self.parse(arg_pc)?);
        }
        Ok(Expr::App(items))
    }

    fn parse_lambda(&mut self, pc: usize) -> Result<Expr, Red2Error> {
        let mut params = Vec::new();
        let mut cursor = pc;
        let arity = lambda_arity(self.program.metadata.get(&format!("lambda:{pc}:arity")));
        while let Some(inst) = self.program.instructions.get(cursor) {
            if inst.opcode != Opcode::Lambda || arity.is_some_and(|limit| params.len() >= limit) {
                break;
            }
            match &inst.data {
                Data::String(name) => params.push(name.clone()),
                _ => params.push(format!("arg{cursor}")),
            }
            cursor += 1;
        }
        Ok(Expr::Lambda(params, Box::new(self.parse(cursor)?)))
    }

    fn parse_struct(&mut self, pc: usize) -> Result<Expr, Red2Error> {
        let inst = self
            .program
            .instructions
            .get(pc)
            .ok_or_else(|| Red2Error(format!("instruction index out of range: {pc}")))?;
        let Data::String(tag) = &inst.data else {
            return Err(Red2Error("STRUCT requires string data".to_string()));
        };
        let mut field_pcs = Vec::new();
        let mut cursor = pc + 1;
        while let Some(inst) = self.program.instructions.get(cursor) {
            if inst.opcode != Opcode::App {
                break;
            }
            let Data::Int(field_pc) = inst.data else {
                return Err(Red2Error(
                    "STRUCT field APP requires integer data".to_string(),
                ));
            };
            field_pcs.push(field_pc as usize);
            cursor += 1;
        }
        match self
            .program
            .instructions
            .get(cursor)
            .map(|inst| inst.opcode)
        {
            Some(Opcode::Var) => {}
            _ => return Err(Red2Error("STRUCT requires trailing VAR body".to_string())),
        }
        let mut fields = Vec::with_capacity(field_pcs.len());
        for field_pc in field_pcs.into_iter().rev() {
            fields.push(self.parse(field_pc)?);
        }
        if tag == "PAIR" && fields.len() == 2 {
            return Ok(Expr::Pair(
                Box::new(fields.remove(0)),
                Box::new(fields.remove(0)),
            ));
        }
        let mut items = vec![Expr::Symbol(tag.clone())];
        items.extend(fields);
        Ok(Expr::App(items))
    }
}

fn lambda_arity(metadata: Option<&Vec<String>>) -> Option<usize> {
    let values = metadata?;
    if values.len() != 1 {
        return None;
    }
    values[0].parse().ok()
}

fn instruction_expr(inst: &Instruction) -> Result<Expr, Red2Error> {
    match inst.opcode {
        Opcode::Int => match inst.data {
            Data::Int(value) => Ok(Expr::Int(i64::from(value))),
            _ => Err(Red2Error("INT requires integer data".to_string())),
        },
        Opcode::Float => match inst.data {
            Data::Float(value) => Ok(Expr::Float(value)),
            _ => Err(Red2Error("FLOAT requires float data".to_string())),
        },
        Opcode::Char => match &inst.data {
            Data::String(value) => Ok(Expr::Char(value.clone())),
            _ => Err(Red2Error("CHAR requires string data".to_string())),
        },
        Opcode::Sym | Opcode::Prim0 | Opcode::Prim1 | Opcode::Prim2 => match &inst.data {
            Data::String(value) => Ok(Expr::Symbol(value.clone())),
            _ => Err(Red2Error(
                "symbol instruction requires string data".to_string(),
            )),
        },
        Opcode::Stop => Ok(Expr::Symbol("STOP".to_string())),
        other => Err(Red2Error(format!("unsupported opcode: {other:?}"))),
    }
}

struct Reducer<'a> {
    bundle: Option<&'a ProgramBundle>,
    parsed_definitions: BTreeMap<String, Expr>,
    remaining: u32,
    steps: u32,
}

impl Reducer<'_> {
    fn reduce(&mut self, expr: Expr, env: &[Expr]) -> Result<Expr, Red2Error> {
        let mut expr = expr;
        let mut env = env.to_vec();
        loop {
            match expr {
                Expr::Var(index, _) => match env.get(index) {
                    Some(Expr::Closure(closure_expr, captured_env)) => {
                        expr = (**closure_expr).clone();
                        env = captured_env.clone();
                    }
                    Some(value) => {
                        expr = value.clone();
                    }
                    None => return Ok(Expr::Var(index, None)),
                },
                Expr::Closure(next_expr, captured_env) => match *next_expr {
                    Expr::Lambda(params, body) => {
                        return Ok(Expr::Closure(
                            Box::new(Expr::Lambda(params, body)),
                            captured_env,
                        ));
                    }
                    next => {
                        expr = next;
                        env = captured_env;
                    }
                },
                Expr::Symbol(name) => {
                    if self.definition_expr(&name)?.is_some() {
                        if self.remaining == 0 {
                            return Ok(Expr::Symbol(name));
                        }
                        self.contract();
                        expr = self
                            .definition_expr(&name)?
                            .expect("definition checked above");
                        env.clear();
                    } else {
                        return Ok(Expr::Symbol(name));
                    }
                }
                Expr::App(items) => match self.reduce_app_step(items, &env)? {
                    ReduceStep::Return(value) => return Ok(value),
                    ReduceStep::TailCall(next_expr, next_env) => {
                        expr = next_expr;
                        env = next_env;
                    }
                },
                Expr::Lambda(params, body) => {
                    if env.is_empty() {
                        return Ok(Expr::Lambda(params, body));
                    }
                    return Ok(Expr::Closure(Box::new(Expr::Lambda(params, body)), env));
                }
                value => return Ok(value),
            }
        }
    }

    fn definition_expr(&mut self, name: &str) -> Result<Option<Expr>, Red2Error> {
        if let Some(expr) = self.parsed_definitions.get(name) {
            return Ok(Some(expr.clone()));
        }
        let Some(program) = self.bundle.and_then(|bundle| bundle.definition(name)) else {
            return Ok(None);
        };
        let mut parser = Parser { program };
        let expr = parser.parse(program.entry as usize)?;
        self.parsed_definitions
            .insert(name.to_string(), expr.clone());
        Ok(Some(expr))
    }

    fn reduce_app_step(&mut self, items: Vec<Expr>, env: &[Expr]) -> Result<ReduceStep, Red2Error> {
        if items.is_empty() {
            return Ok(ReduceStep::Return(Expr::App(items)));
        }
        let operator = self.reduce(items[0].clone(), env)?;
        let args = items[1..].to_vec();
        if let Expr::Symbol(name) = &operator {
            match (name.as_str(), args.as_slice()) {
                ("IF", [condition, consequent, alternative]) => {
                    let condition = self.reduce(condition.clone(), env)?;
                    if is_true(&condition) {
                        return Ok(ReduceStep::TailCall(consequent.clone(), env.to_vec()));
                    }
                    if is_false(&condition) {
                        return Ok(ReduceStep::TailCall(alternative.clone(), env.to_vec()));
                    }
                    return Err(Red2Error(format!(
                        "IF condition is stuck: {}",
                        condition.to_source()
                    )));
                }
                ("AND", [left, right]) => {
                    let left = self.reduce(left.clone(), env)?;
                    if is_false(&left) {
                        return Ok(ReduceStep::Return(Expr::Symbol("FALSE".to_string())));
                    }
                    if is_true(&left) {
                        return Ok(ReduceStep::TailCall(right.clone(), env.to_vec()));
                    }
                    return Err(Red2Error(format!(
                        "AND argument 1 is stuck: {}",
                        left.to_source()
                    )));
                }
                ("OR", [left, right]) => {
                    let left = self.reduce(left.clone(), env)?;
                    if is_true(&left) {
                        return Ok(ReduceStep::Return(Expr::Symbol("TRUE".to_string())));
                    }
                    if is_false(&left) {
                        return Ok(ReduceStep::TailCall(right.clone(), env.to_vec()));
                    }
                    return Err(Red2Error(format!(
                        "OR argument 1 is stuck: {}",
                        left.to_source()
                    )));
                }
                ("Y", [arg]) => {
                    if self.remaining == 0 {
                        return Ok(ReduceStep::Return(Expr::App(items)));
                    }
                    self.contract();
                    let recursive_call =
                        Expr::App(vec![Expr::Symbol("Y".to_string()), arg.clone()]);
                    return Ok(ReduceStep::TailCall(
                        Expr::App(vec![arg.clone(), recursive_call]),
                        env.to_vec(),
                    ));
                }
                _ => {}
            }
            if let Some(value) = self.try_primitive(name, &args, env)? {
                return Ok(ReduceStep::Return(value));
            }
        }
        if let Some((params, body, lambda_env)) = lambda_parts(operator.clone()) {
            if !params.is_empty() && !args.is_empty() && self.remaining > 0 {
                let bind_count = params.len().min(args.len()).min(self.remaining as usize);
                if bind_count == 0 {
                    return Ok(ReduceStep::Return(Expr::App(items)));
                }
                for _ in 0..bind_count {
                    self.contract();
                }
                let mut next_env = Vec::with_capacity(bind_count + lambda_env.len());
                for arg in &args[..bind_count] {
                    next_env.push(Expr::Closure(Box::new(arg.clone()), env.to_vec()));
                }
                extend_needed_outer_env(&mut next_env, &body, bind_count, &lambda_env);
                if bind_count == params.len() && bind_count == args.len() {
                    return Ok(ReduceStep::TailCall(*body, next_env));
                }
                let reduced = if bind_count == params.len() {
                    self.reduce(*body, &next_env)?
                } else {
                    Expr::Closure(
                        Box::new(Expr::Lambda(params[bind_count..].to_vec(), body)),
                        next_env,
                    )
                };
                if bind_count == args.len() {
                    return Ok(ReduceStep::Return(reduced));
                }
                let mut next_items = vec![reduced];
                next_items.extend_from_slice(&args[bind_count..]);
                return Ok(ReduceStep::TailCall(Expr::App(next_items), env.to_vec()));
            }
        }
        let mut rebuilt = vec![operator];
        rebuilt.extend(args);
        Ok(ReduceStep::Return(Expr::App(rebuilt)))
    }

    fn try_primitive(
        &mut self,
        name: &str,
        args: &[Expr],
        env: &[Expr],
    ) -> Result<Option<Expr>, Red2Error> {
        if self.remaining == 0 {
            return Ok(None);
        }
        if args.len() == 1 {
            let value = self.reduce(args[0].clone(), env)?;
            let result = match (name, &value) {
                ("1-", Expr::Int(a)) => Some(Expr::Int(a - 1)),
                ("MINUS", Expr::Int(a)) => Some(Expr::Int(-a)),
                ("NOT", value) if is_true(value) => Some(Expr::Symbol("FALSE".to_string())),
                ("NOT", value) if is_false(value) => Some(Expr::Symbol("TRUE".to_string())),
                ("CAR", Expr::Pair(car, _)) => Some((**car).clone()),
                ("CDR", Expr::Pair(_, cdr)) => Some((**cdr).clone()),
                ("NULL?", Expr::Symbol(value)) if value == "NIL" => {
                    Some(Expr::Symbol("TRUE".to_string()))
                }
                ("NULL?", Expr::Pair(_, _)) => Some(Expr::Symbol("FALSE".to_string())),
                ("NULL?", _) => Some(Expr::Symbol("FALSE".to_string())),
                _ => None,
            };
            if result.is_some() {
                self.contract();
                return Ok(result);
            }
            if is_unary_primitive(name) {
                return Err(Red2Error(format!(
                    "primitive {name} argument 1 is stuck: {}",
                    value.to_source()
                )));
            }
            return Ok(None);
        }
        if args.len() != 2 {
            return Ok(None);
        }
        let left = self.reduce(args[0].clone(), env)?;
        let right = self.reduce(args[1].clone(), env)?;
        let result = match (name, &left, &right) {
            ("+", Expr::Int(a), Expr::Int(b)) => Some(Expr::Int(a + b)),
            ("-", Expr::Int(a), Expr::Int(b)) => Some(Expr::Int(a - b)),
            ("*", Expr::Int(a), Expr::Int(b)) => Some(Expr::Int(a * b)),
            ("/", Expr::Int(a), Expr::Int(b)) if *b != 0 => Some(Expr::Int(a / b)),
            ("MOD", Expr::Int(a), Expr::Int(b)) if *b != 0 => Some(Expr::Int(a % b)),
            ("<", Expr::Int(a), Expr::Int(b)) => Some(bool_expr(a < b)),
            (">", Expr::Int(a), Expr::Int(b)) => Some(bool_expr(a > b)),
            ("<=", Expr::Int(a), Expr::Int(b)) => Some(bool_expr(a <= b)),
            (">=", Expr::Int(a), Expr::Int(b)) => Some(bool_expr(a >= b)),
            ("=", left, right) => constant_equal(left, right).map(bool_expr),
            ("EQUAL?", left, right) => Some(bool_expr(left == right)),
            ("CONS", left, right) => {
                Some(Expr::Pair(Box::new(left.clone()), Box::new(right.clone())))
            }
            _ => None,
        };
        if result.is_some() {
            self.contract();
            return Ok(result);
        }
        if is_binary_primitive(name) {
            let (index, value) = if !is_supported_binary_arg(name, &left) {
                (1, left)
            } else {
                (2, right)
            };
            return Err(Red2Error(format!(
                "primitive {name} argument {index} is stuck: {}",
                value.to_source()
            )));
        }
        Ok(None)
    }

    fn contract(&mut self) {
        self.remaining -= 1;
        self.steps += 1;
    }
}

enum ReduceStep {
    Return(Expr),
    TailCall(Expr, Vec<Expr>),
}

struct IoRunner<'a, R: Read, W: Write, C: ClockSource> {
    reducer: Reducer<'a>,
    quantum: u32,
    input: &'a mut R,
    output: &'a mut W,
    clock: &'a mut C,
}

impl<R: Read, W: Write, C: ClockSource> IoRunner<'_, R, W, C> {
    fn run_action(&mut self, expr: Expr, env: &[Expr]) -> Result<Expr, Red2Error> {
        self.run_action_loop(expr, env.to_vec())
    }

    fn reduce_pure(&mut self, expr: Expr, env: &[Expr]) -> Result<Expr, Red2Error> {
        self.reducer.remaining = self.quantum;
        self.reducer.reduce(expr, env)
    }

    fn run_action_loop(&mut self, mut expr: Expr, mut env: Vec<Expr>) -> Result<Expr, Red2Error> {
        let mut frames = Vec::new();
        loop {
            let current = std::mem::replace(&mut expr, Expr::Symbol("__INVALID__".to_string()));
            match current {
                Expr::Var(index, _) => match env.get(index) {
                    Some(Expr::Closure(closure_expr, captured_env)) => {
                        expr = (**closure_expr).clone();
                        env = captured_env.clone();
                    }
                    Some(value) => {
                        expr = value.clone();
                    }
                    None => return Err(Red2Error(format!("unbound IO variable: {index}"))),
                },
                Expr::Closure(next_expr, captured_env) => {
                    expr = *next_expr;
                    env = captured_env;
                }
                Expr::Symbol(name) => {
                    if name == "UART-RX" {
                        let value = self.read_uart_rx()?;
                        if let Some(final_value) =
                            self.continue_after_value(value, &mut expr, &mut env, &mut frames)?
                        {
                            return Ok(final_value);
                        }
                    } else if name == "CLOCK" {
                        let value = Expr::Int(self.clock.now_ms());
                        if let Some(final_value) =
                            self.continue_after_value(value, &mut expr, &mut env, &mut frames)?
                        {
                            return Ok(final_value);
                        }
                    } else if let Some(next_expr) = self.reducer.definition_expr(&name)? {
                        expr = next_expr;
                        env.clear();
                    } else {
                        return Err(Red2Error(format!("not an IO action: {name}")));
                    }
                }
                Expr::App(items) => match self.step_app(items, &env, &mut frames)? {
                    IoStep::Return(value) => {
                        if let Some(final_value) =
                            self.continue_after_value(value, &mut expr, &mut env, &mut frames)?
                        {
                            return Ok(final_value);
                        }
                    }
                    IoStep::TailCall(next_expr, next_env) => {
                        expr = next_expr;
                        env = next_env;
                    }
                },
                other => {
                    return Err(Red2Error(format!(
                        "not an IO action: {}",
                        other.to_source()
                    )));
                }
            }
        }
    }

    fn continue_after_value(
        &mut self,
        value: Expr,
        expr: &mut Expr,
        env: &mut Vec<Expr>,
        frames: &mut Vec<IoFrame>,
    ) -> Result<Option<Expr>, Red2Error> {
        match frames.pop() {
            Some(IoFrame::Then(second, frame_env)) => {
                *expr = second;
                *env = frame_env;
                Ok(None)
            }
            Some(IoFrame::Bind(continuation, frame_env)) => {
                let (next_expr, next_env) =
                    self.apply_unary_action(continuation, value, &frame_env)?;
                *expr = next_expr;
                *env = next_env;
                Ok(None)
            }
            None => Ok(Some(value)),
        }
    }

    fn step_app(
        &mut self,
        items: Vec<Expr>,
        env: &[Expr],
        frames: &mut Vec<IoFrame>,
    ) -> Result<IoStep, Red2Error> {
        if items.is_empty() {
            return Err(Red2Error("not an IO action: ()".to_string()));
        }
        let operator = self.reduce_pure(items[0].clone(), env)?;
        let args = &items[1..];
        if let Expr::Symbol(name) = &operator {
            match (name.as_str(), args) {
                ("IF", [condition, consequent, alternative]) => {
                    let condition = self.reduce_pure(condition.clone(), env)?;
                    if is_true(&condition) {
                        return Ok(IoStep::TailCall(consequent.clone(), env.to_vec()));
                    }
                    if is_false(&condition) {
                        return Ok(IoStep::TailCall(alternative.clone(), env.to_vec()));
                    }
                    return Err(Red2Error(format!(
                        "IF condition is stuck: {}",
                        condition.to_source()
                    )));
                }
                ("IO-RETURN", [value]) => {
                    return self.reduce_pure(value.clone(), env).map(IoStep::Return);
                }
                ("IO-BIND", [action, continuation]) => {
                    frames.push(IoFrame::Bind(continuation.clone(), env.to_vec()));
                    return Ok(IoStep::TailCall(action.clone(), env.to_vec()));
                }
                ("IO-THEN", [first, second]) => {
                    frames.push(IoFrame::Then(second.clone(), env.to_vec()));
                    return Ok(IoStep::TailCall(first.clone(), env.to_vec()));
                }
                ("UART-RX", []) => return self.read_uart_rx().map(IoStep::Return),
                ("CLOCK", []) => return Ok(IoStep::Return(Expr::Int(self.clock.now_ms()))),
                ("UART-TX-BYTES", [value]) => {
                    let value = self.reduce_pure(value.clone(), env)?;
                    self.write_byte_list(&value)?;
                    return Ok(IoStep::Return(Expr::Symbol("NIL".to_string())));
                }
                ("UART-TX", [value]) => {
                    let value = self.reduce_pure(value.clone(), env)?;
                    let Expr::Int(byte) = value else {
                        return Err(Red2Error(format!(
                            "UART-TX argument is stuck: {}",
                            value.to_source()
                        )));
                    };
                    self.output
                        .write_all(&[(byte.rem_euclid(256)) as u8])
                        .map_err(|e| Red2Error(format!("UART-TX failed: {e}")))?;
                    self.output
                        .flush()
                        .map_err(|e| Red2Error(format!("UART-TX flush failed: {e}")))?;
                    return Ok(IoStep::Return(Expr::Symbol("NIL".to_string())));
                }
                _ => {}
            }
        }
        if let Some((params, body, lambda_env)) = lambda_parts(operator) {
            if params.len() != args.len() {
                return Err(Red2Error(format!(
                    "expected {} argument(s), got {}",
                    params.len(),
                    args.len()
                )));
            }
            let mut next_env = Vec::with_capacity(args.len() + lambda_env.len());
            for arg in args {
                next_env.push(self.reduce_pure(arg.clone(), env)?);
            }
            extend_needed_outer_env(&mut next_env, &body, params.len(), &lambda_env);
            return Ok(IoStep::TailCall(*body, next_env));
        }
        let original = Expr::App(items);
        let reduced = self.reduce_pure(original.clone(), env)?;
        if reduced != original {
            return Ok(IoStep::TailCall(reduced, Vec::new()));
        }
        Err(Red2Error(format!(
            "unknown IO action: {}",
            original.to_source()
        )))
    }

    fn read_uart_rx(&mut self) -> Result<Expr, Red2Error> {
        let mut byte = [0u8; 1];
        let read = match self.input.read(&mut byte) {
            Ok(read) => read,
            Err(error) if error.kind() == ErrorKind::WouldBlock => {
                return Ok(Expr::Symbol("NIL".to_string()));
            }
            Err(error) => return Err(Red2Error(format!("UART-RX failed: {error}"))),
        };
        if read == 0 {
            return Ok(Expr::Symbol("NIL".to_string()));
        }
        Ok(Expr::Int(i64::from(byte[0])))
    }

    fn write_byte_list(&mut self, value: &Expr) -> Result<(), Red2Error> {
        let mut cursor = value;
        loop {
            match cursor {
                Expr::Pair(head, tail) => {
                    let Expr::Int(byte) = **head else {
                        return Err(Red2Error(format!(
                            "UART-TX-BYTES expects integer bytes, got {}",
                            head.to_source()
                        )));
                    };
                    self.output
                        .write_all(&[(byte.rem_euclid(256)) as u8])
                        .map_err(|e| Red2Error(format!("UART-TX-BYTES failed: {e}")))?;
                    cursor = tail;
                }
                Expr::Symbol(name) if name == "NIL" => {
                    self.output
                        .flush()
                        .map_err(|e| Red2Error(format!("UART-TX-BYTES flush failed: {e}")))?;
                    return Ok(());
                }
                other => {
                    return Err(Red2Error(format!(
                        "UART-TX-BYTES expects a byte list, got {}",
                        other.to_source()
                    )));
                }
            }
        }
    }

    fn apply_unary_action(
        &mut self,
        continuation: Expr,
        value: Expr,
        env: &[Expr],
    ) -> Result<(Expr, Vec<Expr>), Red2Error> {
        let continuation = self.reduce_pure(continuation, env)?;
        let Some((params, body, lambda_env)) = lambda_parts(continuation.clone()) else {
            return Err(Red2Error(format!(
                "IO-BIND expects unary lambda, got {}",
                continuation.to_source()
            )));
        };
        if params.len() != 1 {
            return Err(Red2Error(format!(
                "IO-BIND expects unary lambda, got arity {}",
                params.len()
            )));
        }
        let mut next_env = vec![value];
        extend_needed_outer_env(&mut next_env, &body, 1, &lambda_env);
        Ok((*body, next_env))
    }
}

enum IoFrame {
    Bind(Expr, Vec<Expr>),
    Then(Expr, Vec<Expr>),
}

enum IoStep {
    Return(Expr),
    TailCall(Expr, Vec<Expr>),
}

fn lambda_parts(expr: Expr) -> Option<(Vec<String>, Box<Expr>, Vec<Expr>)> {
    match expr {
        Expr::Lambda(params, body) => Some((params, body, Vec::new())),
        Expr::Closure(expr, env) => match *expr {
            Expr::Lambda(params, body) => Some((params, body, env)),
            _ => None,
        },
        _ => None,
    }
}

fn extend_needed_outer_env(
    next_env: &mut Vec<Expr>,
    body: &Expr,
    bound_count: usize,
    env: &[Expr],
) {
    let needed = required_outer_env(body, bound_count);
    next_env.extend(env.iter().take(needed).cloned());
}

fn required_outer_env(expr: &Expr, bound_count: usize) -> usize {
    max_var_index(expr)
        .map(|index| index.saturating_add(1).saturating_sub(bound_count))
        .unwrap_or(0)
}

fn max_var_index(expr: &Expr) -> Option<usize> {
    match expr {
        Expr::Var(index, _) => Some(*index),
        Expr::Lambda(params, body) => {
            max_var_index(body).and_then(|index| index.checked_sub(params.len()))
        }
        Expr::App(items) => items.iter().filter_map(max_var_index).max(),
        Expr::Pair(car, cdr) => max_var_index(car).max(max_var_index(cdr)),
        Expr::Closure(expr, captured_env) => {
            max_var_index(expr).max(captured_env.iter().filter_map(max_var_index).max())
        }
        Expr::Int(_) | Expr::Float(_) | Expr::Char(_) | Expr::Symbol(_) => None,
    }
}

fn is_unary_primitive(name: &str) -> bool {
    matches!(name, "1-" | "MINUS" | "NOT" | "CAR" | "CDR" | "NULL?")
}

fn is_binary_primitive(name: &str) -> bool {
    matches!(
        name,
        "+" | "-" | "*" | "/" | "MOD" | "<" | ">" | "<=" | ">=" | "=" | "EQUAL?" | "CONS"
    )
}

fn is_supported_binary_arg(name: &str, value: &Expr) -> bool {
    match name {
        "+" | "-" | "*" | "/" | "MOD" | "<" | ">" | "<=" | ">=" => matches!(value, Expr::Int(_)),
        "=" => is_constant(value),
        "EQUAL?" | "CONS" => true,
        _ => false,
    }
}

fn is_constant(value: &Expr) -> bool {
    matches!(
        value,
        Expr::Int(_) | Expr::Float(_) | Expr::Char(_) | Expr::Symbol(_)
    )
}

fn constant_equal(left: &Expr, right: &Expr) -> Option<bool> {
    if !is_constant(left) || !is_constant(right) {
        return None;
    }
    Some(left == right)
}

fn bool_expr(value: bool) -> Expr {
    Expr::Symbol(if value { "TRUE" } else { "FALSE" }.to_string())
}

fn is_true(expr: &Expr) -> bool {
    matches!(expr, Expr::Symbol(name) if name == "TRUE")
}

fn is_false(expr: &Expr) -> bool {
    matches!(expr, Expr::Symbol(name) if name == "FALSE")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bytecode::{Data, Instruction, Opcode, Program, ProgramBundle};
    use std::collections::BTreeMap;

    fn program(instructions: Vec<Instruction>) -> Program {
        Program {
            name: None,
            entry: 0,
            instructions,
            metadata: BTreeMap::new(),
        }
    }

    #[test]
    fn runs_integer_literal() {
        let program = program(vec![Instruction {
            opcode: Opcode::Int,
            head: true,
            data: Data::Int(42),
        }]);
        assert_eq!(run(&program, 10).unwrap().to_source(), "42");
    }

    #[test]
    fn runs_integer_addition_application() {
        let program = program(vec![
            Instruction {
                opcode: Opcode::App,
                head: false,
                data: Data::Int(3),
            },
            Instruction {
                opcode: Opcode::App,
                head: false,
                data: Data::Int(4),
            },
            Instruction {
                opcode: Opcode::Prim2,
                head: false,
                data: Data::String("+".to_string()),
            },
            Instruction {
                opcode: Opcode::Int,
                head: true,
                data: Data::Int(2),
            },
            Instruction {
                opcode: Opcode::Int,
                head: true,
                data: Data::Int(3),
            },
        ]);
        assert_eq!(run(&program, 10).unwrap().to_source(), "5");
    }

    #[test]
    fn runs_unary_minus_and_not_primitives() {
        let minus = program(vec![
            Instruction {
                opcode: Opcode::App,
                head: false,
                data: Data::Int(2),
            },
            Instruction {
                opcode: Opcode::Prim1,
                head: false,
                data: Data::String("MINUS".to_string()),
            },
            Instruction {
                opcode: Opcode::Int,
                head: true,
                data: Data::Int(7),
            },
        ]);
        assert_eq!(run(&minus, 10).unwrap().to_source(), "-7");

        let not = program(vec![
            Instruction {
                opcode: Opcode::App,
                head: false,
                data: Data::Int(2),
            },
            Instruction {
                opcode: Opcode::Prim1,
                head: false,
                data: Data::String("NOT".to_string()),
            },
            Instruction {
                opcode: Opcode::Sym,
                head: true,
                data: Data::String("TRUE".to_string()),
            },
        ]);
        assert_eq!(run(&not, 10).unwrap().to_source(), "FALSE");
    }

    #[test]
    fn preserves_stdout_reserved_result_source_for_lambda_subset() {
        let program = program(vec![
            Instruction {
                opcode: Opcode::App,
                head: false,
                data: Data::Int(4),
            },
            Instruction {
                opcode: Opcode::Lambda,
                head: false,
                data: Data::String("X".to_string()),
            },
            Instruction {
                opcode: Opcode::Var,
                head: true,
                data: Data::Int(0),
            },
            Instruction {
                opcode: Opcode::Stop,
                head: true,
                data: Data::Int(0),
            },
            Instruction {
                opcode: Opcode::Int,
                head: true,
                data: Data::Int(42),
            },
        ]);
        assert_eq!(run(&program, 10).unwrap().to_source(), "42");
    }

    #[test]
    fn latest_file_clock_uses_latest_valid_line_and_keeps_previous_on_bad_input() {
        let path =
            std::env::temp_dir().join(format!("asgard-clock-{}-latest.txt", std::process::id()));
        let _ = std::fs::remove_file(&path);
        std::fs::write(&path, "1700000000123\nnot-a-clock\n1700000000456\n").unwrap();
        let mut clock = LatestFileClockSource::new(path.clone(), 123);

        assert_eq!(clock.now_ms(), 1_700_000_000_456);

        std::fs::write(&path, "bad\n").unwrap();
        assert_eq!(clock.now_ms(), 1_700_000_000_456);
        let _ = std::fs::remove_file(path);
    }

    struct FixedClock(i64);

    impl ClockSource for FixedClock {
        fn now_ms(&mut self) -> i64 {
            self.0
        }
    }

    #[test]
    fn io_clock_action_returns_clock_milliseconds() {
        let program = program(vec![Instruction {
            opcode: Opcode::Sym,
            head: true,
            data: Data::String("CLOCK".to_string()),
        }]);
        let bundle = ProgramBundle {
            entry_index: 0,
            programs: vec![program],
            definitions: BTreeMap::new(),
        };
        let mut input = std::io::empty();
        let mut output = Vec::new();
        let mut clock = FixedClock(1_700_000_000_789);

        assert_eq!(
            run_io_bundle_with_clock(&bundle, 10, &mut input, &mut output, &mut clock)
                .unwrap()
                .to_source(),
            "1700000000789"
        );
        assert!(output.is_empty());
    }
}
