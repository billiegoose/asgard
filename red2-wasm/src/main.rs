use std::env;
use std::fs;

use red2_wasm::bytecode::Program;
use red2_wasm::vm;

fn main() {
    let mut args = env::args().skip(1);
    let Some(path) = args.next() else {
        eprintln!("usage: red2-wasm <program.red2> [--quantum N]");
        std::process::exit(2);
    };
    let mut quantum = 100u32;
    while let Some(arg) = args.next() {
        if arg == "--quantum" {
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
    match Program::decode(&bytes).and_then(|program| vm::run(&program, quantum)) {
        Ok(result) => eprintln!("red2 result: {}", result.to_source()),
        Err(error) => {
            eprintln!("red2-wasm: {error}");
            std::process::exit(2);
        }
    }
}
