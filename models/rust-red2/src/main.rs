use std::env;
use std::fs;
use std::io;

use red2_wasm::bytecode::ProgramBundle;
use red2_wasm::vm::{self, Expr};

enum RunOutcome {
    Io(Expr),
    Red2(Expr),
}

fn main() {
    let mut args = env::args().skip(1);
    let Some(path) = args.next() else {
        eprintln!("usage: red2-wasm <program.red2> [--quantum N] [--clock PATH] [--verbose]");
        std::process::exit(2);
    };
    let mut quantum = 100u32;
    let mut verbose = false;
    let mut clock_path: Option<String> = None;
    while let Some(arg) = args.next() {
        if arg == "--verbose" {
            verbose = true;
        } else if arg == "--quantum" {
            let Some(value) = args.next() else {
                eprintln!("red2-wasm: --quantum requires a value");
                std::process::exit(2);
            };
            quantum = match value.parse() {
                Ok(value) => value,
                Err(error) => {
                    eprintln!("red2-wasm: invalid quantum: {error}");
                    std::process::exit(2);
                }
            };
        } else if arg == "--clock" {
            let Some(value) = args.next() else {
                eprintln!("red2-wasm: --clock requires a value");
                std::process::exit(2);
            };
            clock_path = Some(value);
        } else {
            eprintln!("red2-wasm: unknown argument: {arg}");
            std::process::exit(2);
        }
    }
    let bytes = match fs::read(&path) {
        Ok(bytes) => bytes,
        Err(error) => {
            eprintln!("red2-wasm: {error}");
            std::process::exit(2);
        }
    };
    let result = ProgramBundle::decode(&bytes).and_then(|bundle| {
        let preflight = vm::run_bundle(&bundle, quantum)?;
        if is_io_action(&preflight) {
            let mut stdin = io::stdin().lock();
            let mut stdout = io::stdout().lock();
            if let Some(path) = clock_path {
                let mut system_clock = vm::SystemClockSource;
                let initial_ms = vm::ClockSource::now_ms(&mut system_clock);
                let mut clock = vm::LatestFileClockSource::new(path.into(), initial_ms);
                vm::run_io_bundle_with_clock(&bundle, quantum, &mut stdin, &mut stdout, &mut clock)
                    .map(RunOutcome::Io)
            } else {
                vm::run_io_bundle(&bundle, quantum, &mut stdin, &mut stdout).map(RunOutcome::Io)
            }
        } else {
            Ok(RunOutcome::Red2(preflight))
        }
    });
    match result {
        Ok(RunOutcome::Io(result)) => {
            if verbose {
                eprintln!("io result: {}", result.to_source());
            }
        }
        Ok(RunOutcome::Red2(result)) => {
            if verbose {
                eprintln!("red2 result: {}", result.to_source());
            }
        }
        Err(error) => {
            eprintln!("red2-wasm: {error}");
            std::process::exit(2);
        }
    }
}

fn is_io_action(expr: &Expr) -> bool {
    match expr {
        Expr::Symbol(name) => is_io_action_name(name),
        Expr::App(items) => items.first().is_some_and(
            |operator| matches!(operator, Expr::Symbol(name) if is_io_action_name(name)),
        ),
        _ => false,
    }
}

fn is_io_action_name(name: &str) -> bool {
    matches!(
        name,
        "IF" | "IO-BIND" | "IO-RETURN" | "IO-THEN" | "UART-RX" | "UART-TX"
            | "UART-TX-BYTES" | "CLOCK"
    )
}
