use std::collections::BTreeMap;
use std::fmt;

pub const MAGIC: &[u8; 4] = b"RED2";
const VERSION: u16 = 2;
const HEADER_SIZE: usize = 36;
const CHECKSUM_SIZE: usize = 4;
const INSTRUCTION_SIZE: usize = 8;
const PROGRAM_SIZE: usize = 16;
const SENTINEL_NAME: u32 = 0xFFFF_FFFF;
const KIND_INT: u16 = 0;
const KIND_STRING: u16 = 1;
const KIND_FLOAT: u16 = 2;
const KIND_NONE: u16 = 3;
const LITERAL_STRING: u8 = 1;
const LITERAL_FLOAT: u8 = 2;

#[derive(Debug, Clone, PartialEq)]
pub struct Red2Error(pub String);

impl fmt::Display for Red2Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for Red2Error {}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Opcode {
    App = 0,
    Lambda = 1,
    Var = 2,
    Stop = 3,
    Int = 4,
    Float = 5,
    Char = 6,
    Sym = 7,
    Prim0 = 8,
    Prim1 = 9,
    Prim2 = 10,
    Struct = 11,
    Rblock = 12,
    Rup = 13,
    Recp = 14,
    Join = 15,
    Closure = 16,
    Ubv = 17,
    Pnp = 18,
    Rec = 19,
}

impl Opcode {
    fn from_u8(value: u8) -> Result<Self, Red2Error> {
        match value {
            0 => Ok(Self::App),
            1 => Ok(Self::Lambda),
            2 => Ok(Self::Var),
            3 => Ok(Self::Stop),
            4 => Ok(Self::Int),
            5 => Ok(Self::Float),
            6 => Ok(Self::Char),
            7 => Ok(Self::Sym),
            8 => Ok(Self::Prim0),
            9 => Ok(Self::Prim1),
            10 => Ok(Self::Prim2),
            11 => Ok(Self::Struct),
            12 => Ok(Self::Rblock),
            13 => Ok(Self::Rup),
            14 => Ok(Self::Recp),
            15 => Ok(Self::Join),
            16 => Ok(Self::Closure),
            17 => Ok(Self::Ubv),
            18 => Ok(Self::Pnp),
            19 => Ok(Self::Rec),
            _ => Err(Red2Error(format!("unknown opcode value: {value}"))),
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum Data {
    Int(i32),
    String(String),
    Float(f64),
    None,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Instruction {
    pub opcode: Opcode,
    pub head: bool,
    pub data: Data,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Literal {
    String(String),
    Float(f64),
}

#[derive(Debug, Clone, PartialEq)]
pub struct Program {
    pub name: Option<String>,
    pub entry: u32,
    pub instructions: Vec<Instruction>,
    pub metadata: BTreeMap<String, Vec<String>>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ProgramBundle {
    pub entry_index: usize,
    pub programs: Vec<Program>,
    pub definitions: BTreeMap<String, usize>,
}

impl Program {
    pub fn decode(bytes: &[u8]) -> Result<Self, Red2Error> {
        let bundle = ProgramBundle::decode(bytes)?;
        bundle
            .entry()
            .cloned()
            .ok_or_else(|| Red2Error("missing entry program".to_string()))
    }
}

impl ProgramBundle {
    pub fn decode(bytes: &[u8]) -> Result<Self, Red2Error> {
        if bytes.len() < HEADER_SIZE + CHECKSUM_SIZE {
            return Err(Red2Error("RED2 bytecode too short".to_string()));
        }
        if &bytes[0..4] != MAGIC {
            return Err(Red2Error("bad RED2 magic".to_string()));
        }
        let version = read_u16(bytes, 4)?;
        if version != VERSION {
            return Err(Red2Error(format!(
                "unsupported RED2 bytecode version: {version}"
            )));
        }
        let stored_crc = read_u32(bytes, bytes.len() - CHECKSUM_SIZE)?;
        let body = &bytes[..bytes.len() - CHECKSUM_SIZE];
        let actual_crc = crc32(body);
        if stored_crc != actual_crc {
            return Err(Red2Error("RED2 bytecode checksum mismatch".to_string()));
        }

        let entry_index = read_u32(bytes, 8)? as usize;
        let program_count = read_u32(bytes, 12)? as usize;
        let literal_count = read_u32(bytes, 16)? as usize;
        let meta_count = read_u32(bytes, 20)? as usize;
        if meta_count != 0 {
            return Err(Red2Error(
                "global metadata records are reserved in RED2 v2".to_string(),
            ));
        }
        let mut offset = HEADER_SIZE;
        let mut raw_programs = Vec::with_capacity(program_count);
        for _ in 0..program_count {
            ensure(bytes, offset, PROGRAM_SIZE)?;
            let name_index = read_u32(bytes, offset)?;
            let entry = read_u32(bytes, offset + 4)?;
            let word_count = read_u32(bytes, offset + 8)? as usize;
            let program_meta_count = read_u32(bytes, offset + 12)? as usize;
            offset += PROGRAM_SIZE;
            let mut raw_words = Vec::with_capacity(word_count);
            for _ in 0..word_count {
                ensure(bytes, offset, INSTRUCTION_SIZE)?;
                let opcode = Opcode::from_u8(bytes[offset])?;
                let head = (bytes[offset + 1] & 1) != 0;
                let kind = read_u16(bytes, offset + 2)?;
                let data = read_u32(bytes, offset + 4)?;
                raw_words.push((opcode, head, kind, data));
                offset += INSTRUCTION_SIZE;
            }
            let (metadata, next_offset) = decode_metadata(bytes, offset, program_meta_count)?;
            offset = next_offset;
            raw_programs.push((name_index, entry, raw_words, metadata));
        }

        let mut literals = Vec::with_capacity(literal_count);
        for _ in 0..literal_count {
            ensure(bytes, offset, 5)?;
            let kind = bytes[offset];
            let len = read_u32(bytes, offset + 1)? as usize;
            offset += 5;
            ensure(bytes, offset, len)?;
            let payload = &bytes[offset..offset + len];
            offset += len;
            match kind {
                LITERAL_STRING => literals.push(Literal::String(
                    String::from_utf8(payload.to_vec())
                        .map_err(|e| Red2Error(format!("invalid UTF-8 literal: {e}")))?,
                )),
                LITERAL_FLOAT if len == 8 => {
                    let mut raw = [0u8; 8];
                    raw.copy_from_slice(payload);
                    literals.push(Literal::Float(f64::from_le_bytes(raw)));
                }
                _ => return Err(Red2Error(format!("unknown literal kind: {kind}"))),
            }
        }
        if offset != bytes.len() - CHECKSUM_SIZE {
            return Err(Red2Error(
                "RED2 bytecode has trailing or malformed section data".to_string(),
            ));
        }
        if entry_index >= raw_programs.len() {
            return Err(Red2Error(format!(
                "entry program index out of range: {entry_index}"
            )));
        }

        let mut programs = Vec::with_capacity(raw_programs.len());
        let mut definitions = BTreeMap::new();
        for (index, (name_index, entry, raw_words, metadata)) in
            raw_programs.into_iter().enumerate()
        {
            let name = decode_program_name(name_index, &literals)?;
            let mut instructions = Vec::with_capacity(raw_words.len());
            for (opcode, head, kind, data) in raw_words {
                instructions.push(Instruction {
                    opcode,
                    head,
                    data: decode_data(kind, data, &literals)?,
                });
            }
            if let Some(name) = &name {
                definitions.insert(name.clone(), index);
            }
            programs.push(Program {
                name,
                entry,
                instructions,
                metadata,
            });
        }
        Ok(Self {
            entry_index,
            programs,
            definitions,
        })
    }

    pub fn entry(&self) -> Option<&Program> {
        self.programs.get(self.entry_index)
    }

    pub fn definition(&self, name: &str) -> Option<&Program> {
        self.definitions
            .get(name)
            .and_then(|index| self.programs.get(*index))
    }
}

fn decode_program_name(index: u32, literals: &[Literal]) -> Result<Option<String>, Red2Error> {
    if index == SENTINEL_NAME {
        return Ok(None);
    }
    match literals.get(index as usize) {
        Some(Literal::String(value)) => Ok(Some(value.clone())),
        _ => Err(Red2Error(format!(
            "program name literal index out of range: {index}"
        ))),
    }
}

fn decode_data(kind: u16, data: u32, literals: &[Literal]) -> Result<Data, Red2Error> {
    match kind {
        KIND_NONE => Ok(Data::None),
        KIND_INT => Ok(Data::Int(data as i32)),
        KIND_STRING => match literals.get(data as usize) {
            Some(Literal::String(value)) => Ok(Data::String(value.clone())),
            _ => Err(Red2Error(format!("literal index out of range: {data}"))),
        },
        KIND_FLOAT => match literals.get(data as usize) {
            Some(Literal::Float(value)) => Ok(Data::Float(*value)),
            _ => Err(Red2Error(format!("literal index out of range: {data}"))),
        },
        _ => Err(Red2Error(format!("unknown instruction data kind: {kind}"))),
    }
}

fn decode_metadata(
    bytes: &[u8],
    mut offset: usize,
    count: usize,
) -> Result<(BTreeMap<String, Vec<String>>, usize), Red2Error> {
    let mut metadata = BTreeMap::new();
    for _ in 0..count {
        let key_len = read_u16(bytes, offset)? as usize;
        let value_count = read_u16(bytes, offset + 2)? as usize;
        offset += 4;
        ensure(bytes, offset, key_len)?;
        let key = String::from_utf8(bytes[offset..offset + key_len].to_vec())
            .map_err(|e| Red2Error(format!("invalid UTF-8 metadata key: {e}")))?;
        offset += key_len;
        let mut values = Vec::with_capacity(value_count);
        for _ in 0..value_count {
            let len = read_u16(bytes, offset)? as usize;
            offset += 2;
            ensure(bytes, offset, len)?;
            values.push(
                String::from_utf8(bytes[offset..offset + len].to_vec())
                    .map_err(|e| Red2Error(format!("invalid UTF-8 metadata value: {e}")))?,
            );
            offset += len;
        }
        metadata.insert(key, values);
    }
    Ok((metadata, offset))
}

fn ensure(bytes: &[u8], offset: usize, len: usize) -> Result<(), Red2Error> {
    if offset + len > bytes.len() {
        return Err(Red2Error("truncated RED2 bytecode".to_string()));
    }
    Ok(())
}

fn read_u16(bytes: &[u8], offset: usize) -> Result<u16, Red2Error> {
    ensure(bytes, offset, 2)?;
    Ok(u16::from_le_bytes([bytes[offset], bytes[offset + 1]]))
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, Red2Error> {
    ensure(bytes, offset, 4)?;
    Ok(u32::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
    ]))
}

pub fn crc32(bytes: &[u8]) -> u32 {
    let mut crc = 0xFFFF_FFFFu32;
    for byte in bytes {
        crc ^= u32::from(*byte);
        for _ in 0..8 {
            let mask = 0u32.wrapping_sub(crc & 1);
            crc = (crc >> 1) ^ (0xEDB8_8320 & mask);
        }
    }
    !crc
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_bundle() -> Vec<u8> {
        let mut body = Vec::new();
        body.extend_from_slice(MAGIC);
        body.extend_from_slice(&VERSION.to_le_bytes());
        body.extend_from_slice(&0u16.to_le_bytes());
        body.extend_from_slice(&0u32.to_le_bytes());
        body.extend_from_slice(&1u32.to_le_bytes());
        body.extend_from_slice(&0u32.to_le_bytes());
        body.extend_from_slice(&0u32.to_le_bytes());
        body.extend_from_slice(&0u32.to_le_bytes());
        body.extend_from_slice(&[0u8; 8]);
        body.extend_from_slice(&SENTINEL_NAME.to_le_bytes());
        body.extend_from_slice(&0u32.to_le_bytes());
        body.extend_from_slice(&2u32.to_le_bytes());
        body.extend_from_slice(&0u32.to_le_bytes());
        body.extend_from_slice(&[4, 1, 0, 0, 42, 0, 0, 0]);
        body.extend_from_slice(&[3, 1, 0, 0, 0, 0, 0, 0]);
        let crc = crc32(&body);
        body.extend_from_slice(&crc.to_le_bytes());
        body
    }

    #[test]
    fn parses_sample_bundle() {
        let bundle = ProgramBundle::decode(&sample_bundle()).unwrap();
        assert_eq!(bundle.entry_index, 0);
        assert_eq!(bundle.entry().unwrap().instructions.len(), 2);
        assert_eq!(bundle.entry().unwrap().instructions[0].opcode, Opcode::Int);
        assert_eq!(bundle.entry().unwrap().instructions[0].data, Data::Int(42));
    }

    #[test]
    fn parses_sample_program_wrapper() {
        let program = Program::decode(&sample_bundle()).unwrap();
        assert_eq!(program.entry, 0);
        assert_eq!(program.instructions[0].data, Data::Int(42));
    }

    #[test]
    fn rejects_bad_magic() {
        let mut bytes = sample_bundle();
        bytes[0..4].copy_from_slice(b"NOPE");
        let error = ProgramBundle::decode(&bytes).unwrap_err();
        assert!(error.to_string().contains("bad RED2 magic"));
    }

    #[test]
    fn rejects_bad_checksum() {
        let mut bytes = sample_bundle();
        let last = bytes.len() - 1;
        bytes[last] ^= 0xff;
        let error = ProgramBundle::decode(&bytes).unwrap_err();
        assert!(error.to_string().contains("checksum"));
    }
}
