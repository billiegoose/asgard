use std::env;
use std::fs;
use std::io;

use red2_wasm::bytecode::ProgramBundle;
use red2_wasm::vm;

fn main() {
    let mut args = env::args().skip(1);
    let Some(path) = args.next() else {
        eprintln!("usage: red2-wasm <program.red2> [--quantum N]");
        std::process::exit(2);
    };
    let mut quantum = 100u32;
    let mut io_mode = false;
    while let Some(arg) = args.next() {
        if arg == "--io" {
            io_mode = true;
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
        if io_mode {
            let mut stdin = io::stdin().lock();
            let mut stdout = io::stdout().lock();
            vm::run_io_bundle(&bundle, quantum, &mut stdin, &mut stdout)
        } else {
            vm::run_bundle(&bundle, quantum)
        }
    });
    match result {
        Ok(result) if io_mode => eprintln!("io result: {}", result.to_source()),
        Ok(result) => eprintln!("red2 result: {}", result.to_source()),
        Err(error) => {
            eprintln!("red2-wasm: {error}");
            std::process::exit(2);
        }
    }
}
