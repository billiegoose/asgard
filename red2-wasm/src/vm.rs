use crate::bytecode::{Data, Instruction, Opcode, Program, Red2Error};

#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Int(i32),
    Float(f64),
    Char(String),
    Symbol(String),
    Var(usize, Option<String>),
    Lambda(Vec<String>, Box<Expr>),
    App(Vec<Expr>),
}

impl Expr {
    pub fn to_source(&self) -> String {
        match self {
            Expr::Int(value) => value.to_string(),
            Expr::Float(value) => value.to_string(),
            Expr::Char(value) => format!("#\\{value}"),
            Expr::Symbol(value) => value.clone(),
            Expr::Var(_, Some(name)) => name.clone(),
            Expr::Var(index, None) => format!("(VAR {index})"),
            Expr::Lambda(params, body) => {
                format!("(LAMBDA ({}) {})", params.join(" "), body.to_source())
            }
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

pub fn run(program: &Program, quantum: u32) -> Result<Expr, Red2Error> {
    let mut parser = Parser { program };
    let expr = parser.parse(program.entry as usize)?;
    let mut reducer = Reducer {
        remaining: quantum,
        steps: 0,
    };
    reducer.reduce(expr, &[])
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
}

fn instruction_expr(inst: &Instruction) -> Result<Expr, Red2Error> {
    match inst.opcode {
        Opcode::Int => match inst.data {
            Data::Int(value) => Ok(Expr::Int(value)),
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

struct Reducer {
    remaining: u32,
    steps: u32,
}

impl Reducer {
    fn reduce(&mut self, expr: Expr, env: &[Expr]) -> Result<Expr, Red2Error> {
        match expr {
            Expr::Var(index, _) => Ok(env.get(index).cloned().unwrap_or(Expr::Var(index, None))),
            Expr::App(items) => self.reduce_app(items, env),
            Expr::Lambda(params, body) => Ok(Expr::Lambda(params, body)),
            value => Ok(value),
        }
    }

    fn reduce_app(&mut self, items: Vec<Expr>, env: &[Expr]) -> Result<Expr, Red2Error> {
        if items.is_empty() {
            return Ok(Expr::App(items));
        }
        let operator = self.reduce(items[0].clone(), env)?;
        let args = items[1..].to_vec();
        if let Expr::Symbol(name) = &operator {
            if let Some(value) = self.try_primitive(name, &args, env)? {
                return Ok(value);
            }
        }
        if let Expr::Lambda(params, body) = operator.clone() {
            if !params.is_empty() && !args.is_empty() && self.remaining > 0 {
                self.contract();
                let mut next_env = vec![args[0].clone()];
                next_env.extend_from_slice(env);
                let reduced = if params.len() == 1 {
                    self.reduce(*body, &next_env)?
                } else {
                    Expr::Lambda(params[1..].to_vec(), body)
                };
                if args.len() == 1 {
                    return Ok(reduced);
                }
                let mut next_items = vec![reduced];
                next_items.extend_from_slice(&args[1..]);
                return self.reduce(Expr::App(next_items), env);
            }
        }
        let mut rebuilt = vec![operator];
        rebuilt.extend(args);
        Ok(Expr::App(rebuilt))
    }

    fn try_primitive(
        &mut self,
        name: &str,
        args: &[Expr],
        env: &[Expr],
    ) -> Result<Option<Expr>, Red2Error> {
        if self.remaining == 0 || args.len() != 2 {
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

fn bool_expr(value: bool) -> Expr {
    Expr::Symbol(if value { "TRUE" } else { "FALSE" }.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bytecode::{Data, Instruction, Opcode, Program};

    fn program(instructions: Vec<Instruction>) -> Program {
        Program {
            entry: 0,
            instructions,
            literals: Vec::new(),
            metadata: Vec::new(),
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
}
