use std::collections::BTreeMap;
use std::io::{Read, Write};
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
        Self { path, latest: initial_ms }
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
    let program = bundle
        .entry()
        .ok_or_else(|| Red2Error("missing entry program".to_string()))?;
    let mut parser = Parser { program };
    let expr = parser.parse(program.entry as usize)?;
    let mut reducer = Reducer {
        bundle: Some(bundle),
        parsed_definitions: BTreeMap::new(),
        remaining: quantum,
        steps: 0,
    };
    reducer.reduce(expr, &[])
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
        while let Some(inst) = self.program.instructions.get(cursor) {
            if inst.opcode != Opcode::Lambda {
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
                return Err(Red2Error("STRUCT field APP requires integer data".to_string()));
            };
            field_pcs.push(field_pc as usize);
            cursor += 1;
        }
        match self.program.instructions.get(cursor).map(|inst| inst.opcode) {
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
        match expr {
            Expr::Var(index, _) => match env.get(index) {
                Some(Expr::Closure(expr, captured_env)) => {
                    self.reduce((**expr).clone(), captured_env)
                }
                Some(value) => self.reduce(value.clone(), env),
                None => Ok(Expr::Var(index, None)),
            },
            Expr::Closure(expr, captured_env) => self.reduce(*expr, &captured_env),
            Expr::Symbol(name) => self.resolve_symbol(name),
            Expr::App(items) => self.reduce_app(items, env),
            Expr::Lambda(params, body) => Ok(Expr::Lambda(params, body)),
            value => Ok(value),
        }
    }

    fn resolve_symbol(&mut self, name: String) -> Result<Expr, Red2Error> {
        if self.definition_expr(&name)?.is_some() {
            if self.remaining == 0 {
                return Ok(Expr::Symbol(name));
            }
            self.contract();
            let expr = self
                .definition_expr(&name)?
                .expect("definition checked above");
            return self.reduce(expr, &[]);
        }
        Ok(Expr::Symbol(name))
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

    fn reduce_app(&mut self, items: Vec<Expr>, env: &[Expr]) -> Result<Expr, Red2Error> {
        if items.is_empty() {
            return Ok(Expr::App(items));
        }
        let operator = self.reduce(items[0].clone(), env)?;
        let args = items[1..].to_vec();
        if let Expr::Symbol(name) = &operator {
            if let Some(value) = self.try_control(name, &args, env)? {
                return Ok(value);
            }
            if let Some(value) = self.try_primitive(name, &args, env)? {
                return Ok(value);
            }
        }
        if let Expr::Lambda(params, body) = operator.clone() {
            if !params.is_empty() && !args.is_empty() && self.remaining > 0 {
                let bind_count = params.len().min(args.len()).min(self.remaining as usize);
                if bind_count == 0 {
                    return Ok(Expr::App(items));
                }
                for _ in 0..bind_count {
                    self.contract();
                }
                let mut next_env = Vec::with_capacity(bind_count + env.len());
                for arg in &args[..bind_count] {
                    next_env.push(self.reduce(arg.clone(), env)?);
                }
                next_env.extend_from_slice(env);
                let reduced = if bind_count == params.len() {
                    self.reduce(*body, &next_env)?
                } else {
                    Expr::Closure(
                        Box::new(Expr::Lambda(params[bind_count..].to_vec(), body)),
                        next_env,
                    )
                };
                if bind_count == args.len() {
                    return Ok(reduced);
                }
                let mut next_items = vec![reduced];
                next_items.extend_from_slice(&args[bind_count..]);
                return self.reduce(Expr::App(next_items), env);
            }
        }
        let mut rebuilt = vec![operator];
        rebuilt.extend(args);
        Ok(Expr::App(rebuilt))
    }

    fn try_control(
        &mut self,
        name: &str,
        args: &[Expr],
        env: &[Expr],
    ) -> Result<Option<Expr>, Red2Error> {
        match (name, args) {
            ("IF", [condition, consequent, alternative]) => {
                let condition = self.reduce(condition.clone(), env)?;
                if is_true(&condition) {
                    return self.reduce(consequent.clone(), env).map(Some);
                }
                if is_false(&condition) {
                    return self.reduce(alternative.clone(), env).map(Some);
                }
                Ok(None)
            }
            ("AND", [left, right]) => {
                let left = self.reduce(left.clone(), env)?;
                if is_false(&left) {
                    return Ok(Some(Expr::Symbol("FALSE".to_string())));
                }
                if is_true(&left) {
                    return self.reduce(right.clone(), env).map(Some);
                }
                Ok(None)
            }
            ("OR", [left, right]) => {
                let left = self.reduce(left.clone(), env)?;
                if is_true(&left) {
                    return Ok(Some(Expr::Symbol("TRUE".to_string())));
                }
                if is_false(&left) {
                    return self.reduce(right.clone(), env).map(Some);
                }
                Ok(None)
            }
            _ => Ok(None),
        }
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
            }
            return Ok(result);
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
            ("=", Expr::Int(a), Expr::Int(b)) => Some(bool_expr(a == b)),
            ("EQUAL?", left, right) => Some(bool_expr(left == right)),
            ("CONS", left, right) => {
                Some(Expr::Pair(Box::new(left.clone()), Box::new(right.clone())))
            }
            _ => None,
        };
        if result.is_some() {
            self.contract();
        }
        Ok(result)
    }

    fn contract(&mut self) {
        self.remaining -= 1;
        self.steps += 1;
    }
}

struct IoRunner<'a, R: Read, W: Write, C: ClockSource> {
    reducer: Reducer<'a>,
    input: &'a mut R,
    output: &'a mut W,
    clock: &'a mut C,
}

impl<R: Read, W: Write, C: ClockSource> IoRunner<'_, R, W, C> {
    fn run_action(&mut self, expr: Expr, env: &[Expr]) -> Result<Expr, Red2Error> {
        match expr {
            Expr::Var(index, _) => match env.get(index) {
                Some(Expr::Closure(expr, captured_env)) => {
                    self.run_action((**expr).clone(), captured_env)
                }
                Some(value) => self.run_action(value.clone(), env),
                None => Err(Red2Error(format!("unbound IO variable: {index}"))),
            },
            Expr::Closure(expr, captured_env) => self.run_action(*expr, &captured_env),
            Expr::Symbol(name) => {
                if name == "UART-RX" {
                    let mut byte = [0u8; 1];
                    let read = self
                        .input
                        .read(&mut byte)
                        .map_err(|e| Red2Error(format!("UART-RX failed: {e}")))?;
                    if read == 0 {
                        return Ok(Expr::Symbol("NIL".to_string()));
                    }
                    return Ok(Expr::Int(i64::from(byte[0])));
                }
                if name == "CLOCK" {
                    return Ok(Expr::Int(self.clock.now_ms()));
                }
                if let Some(expr) = self.reducer.definition_expr(&name)? {
                    return self.run_action(expr, &[]);
                }
                Err(Red2Error(format!("not an IO action: {name}")))
            }
            Expr::App(items) => self.run_app(items, env),
            other => Err(Red2Error(format!(
                "not an IO action: {}",
                other.to_source()
            ))),
        }
    }

    fn run_app(&mut self, items: Vec<Expr>, env: &[Expr]) -> Result<Expr, Red2Error> {
        if items.is_empty() {
            return Err(Red2Error("not an IO action: ()".to_string()));
        }
        let operator = self.reducer.reduce(items[0].clone(), env)?;
        let args = &items[1..];
        if let Expr::Symbol(name) = &operator {
            match (name.as_str(), args) {
                ("IF", [condition, consequent, alternative]) => {
                    let condition = self.reducer.reduce(condition.clone(), env)?;
                    if is_true(&condition) {
                        return self.run_action(consequent.clone(), env);
                    }
                    if is_false(&condition) {
                        return self.run_action(alternative.clone(), env);
                    }
                    return Err(Red2Error(format!(
                        "IO IF condition did not reduce to TRUE or FALSE: {}",
                        condition.to_source()
                    )));
                }
                ("IO-RETURN", [value]) => return self.reducer.reduce(value.clone(), env),
                ("IO-BIND", [action, continuation]) => {
                    let value = self.run_action(action.clone(), env)?;
                    return self.apply_unary_action(continuation.clone(), value, env);
                }
                ("IO-THEN", [first, second]) => {
                    self.run_action(first.clone(), env)?;
                    return self.run_action(second.clone(), env);
                }
                ("UART-RX", []) => {
                    let mut byte = [0u8; 1];
                    let read = self
                        .input
                        .read(&mut byte)
                        .map_err(|e| Red2Error(format!("UART-RX failed: {e}")))?;
                    if read == 0 {
                        return Ok(Expr::Symbol("NIL".to_string()));
                    }
                    return Ok(Expr::Int(i64::from(byte[0])));
                }
                ("CLOCK", []) => return Ok(Expr::Int(self.clock.now_ms())),
                ("UART-TX-BYTES", [value]) => {
                    let value = self.reducer.reduce(value.clone(), env)?;
                    self.write_byte_list(&value)?;
                    return Ok(Expr::Symbol("NIL".to_string()));
                }
                ("UART-TX", [value]) => {
                    let value = self.reducer.reduce(value.clone(), env)?;
                    let Expr::Int(byte) = value else {
                        return Err(Red2Error(format!(
                            "UART-TX expects integer byte, got {}",
                            value.to_source()
                        )));
                    };
                    self.output
                        .write_all(&[(byte.rem_euclid(256)) as u8])
                        .map_err(|e| Red2Error(format!("UART-TX failed: {e}")))?;
                    self.output
                        .flush()
                        .map_err(|e| Red2Error(format!("UART-TX flush failed: {e}")))?;
                    return Ok(Expr::Symbol("NIL".to_string()));
                }
                _ => {}
            }
        }
        if let Expr::Lambda(params, body) = operator {
            if params.len() != args.len() {
                return Err(Red2Error(format!(
                    "expected {} argument(s), got {}",
                    params.len(),
                    args.len()
                )));
            }
            let mut next_env = Vec::with_capacity(args.len() + env.len());
            for arg in args {
                next_env.push(self.reducer.reduce(arg.clone(), env)?);
            }
            next_env.extend_from_slice(env);
            return self.run_action(*body, &next_env);
        }
        Err(Red2Error(format!(
            "unknown IO action: {}",
            Expr::App(items).to_source()
        )))
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
    ) -> Result<Expr, Red2Error> {
        let continuation = self.reducer.reduce(continuation, env)?;
        let Expr::Lambda(params, body) = continuation else {
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
        next_env.extend_from_slice(env);
        self.run_action(*body, &next_env)
    }
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
        let path = std::env::temp_dir().join(format!(
            "asgard-clock-{}-latest.txt",
            std::process::id()
        ));
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
