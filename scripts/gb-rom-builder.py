#!/usr/bin/env python3
"""Game Boy ROM Assembler — builds valid .gb ROM files from LR35902 assembly.

Usage:
    python3 scripts/gb-rom-builder.py input.asm -o output.gb [--title TITLE] [--verbose]
    python3 scripts/gb-rom-builder.py --validate input.asm
    python3 scripts/gb-rom-builder.py --tile "00333300,03000030,..."
"""

import argparse
import os
import re
import struct
import sys

# Nintendo logo bytes (required in ROM header)
NINTENDO_LOGO = bytes([
    0xCE, 0xED, 0x66, 0x66, 0xCC, 0x0D, 0x00, 0x0B, 0x03, 0x73, 0x00, 0x83,
    0x00, 0x0C, 0x00, 0x0D, 0x00, 0x08, 0x11, 0x1F, 0x88, 0x89, 0x00, 0x0E,
    0xDC, 0xCC, 0x6E, 0xE6, 0xDD, 0xDD, 0xD9, 0x99, 0xBB, 0xBB, 0x67, 0x63,
    0x6E, 0x0E, 0xEC, 0xCC, 0xDD, 0xDC, 0x99, 0x9F, 0xBB, 0xB9, 0x33, 0x3E,
])

# Register encoding
REG8 = {'B': 0, 'C': 1, 'D': 2, 'E': 3, 'H': 4, 'L': 5, '(HL)': 6, 'A': 7}
REG16 = {'BC': 0, 'DE': 1, 'HL': 2, 'SP': 3}
REG16_PUSH = {'BC': 0, 'DE': 1, 'HL': 2, 'AF': 3}
CONDITIONS = {'NZ': 0, 'Z': 1, 'NC': 2, 'C': 3}

MBC_TYPES = {
    'ROM': 0x00, 'MBC1': 0x01, 'MBC1+RAM': 0x02, 'MBC1+RAM+BATTERY': 0x03,
    'MBC3': 0x11, 'MBC3+RAM': 0x12, 'MBC3+RAM+BATTERY': 0x13,
}

ROM_SIZES = {32: 0, 64: 1, 128: 2, 256: 3, 512: 4, 1024: 5, 2048: 6}


def tile_to_2bpp(rows):
    """Convert 8x8 pixel art (4 colors: 0-3) to 16-byte Game Boy 2bpp tile data."""
    result = bytearray()
    for row in rows:
        if len(row) != 8:
            raise ValueError(f"Tile row must be 8 pixels, got {len(row)}")
        lo = 0
        hi = 0
        for i, ch in enumerate(row):
            color = int(ch)
            if color & 1:
                lo |= (0x80 >> i)
            if color & 2:
                hi |= (0x80 >> i)
        result.append(lo)
        result.append(hi)
    return bytes(result)


def parse_number(s):
    """Parse a number in various formats: $FF, %10101010, 255, 'A'."""
    s = s.strip()
    if s.startswith('$'):
        return int(s[1:], 16)
    if s.startswith('%'):
        return int(s[1:], 2)
    if s.startswith("'") and s.endswith("'") and len(s) == 3:
        return ord(s[1])
    if s.startswith('"') and s.endswith('"') and len(s) == 3:
        return ord(s[1])
    try:
        return int(s)
    except ValueError:
        return None


class Assembler:
    def __init__(self, title="GAME", mbc="ROM", verbose=False):
        self.title = title.upper()[:15]
        self.mbc = mbc
        self.verbose = verbose
        self.labels = {}
        self.constants = {}
        self.output = bytearray(32768)  # 32KB minimum ROM
        self.pc = 0
        self.current_section_addr = None
        self.lines = []
        self.errors = []
        self.warnings = []
        self.current_global_label = ""
        self.fixups = []  # (addr, label, type, line_num)

    def log(self, msg):
        if self.verbose:
            print(f"  [ASM] {msg}")

    def error(self, line_num, msg):
        self.errors.append(f"Error on line {line_num}: {msg}")

    def warn(self, line_num, msg):
        self.warnings.append(f"Warning on line {line_num}: {msg}")

    def resolve_label(self, name):
        """Resolve a label name, handling local labels."""
        if name.startswith('.'):
            full = self.current_global_label + name
            if full in self.labels:
                return self.labels[full]
        if name in self.labels:
            return self.labels[name]
        if name in self.constants:
            return self.constants[name]
        return None

    def emit(self, *bytes_):
        for b in bytes_:
            if self.pc < len(self.output):
                self.output[self.pc] = b & 0xFF
            else:
                self.output.extend(b'\x00' * (self.pc - len(self.output) + 1))
                self.output[self.pc] = b & 0xFF
            self.pc += 1

    def emit16(self, val):
        self.emit(val & 0xFF, (val >> 8) & 0xFF)

    def preprocess(self, source, base_dir="."):
        """Handle includes and strip comments."""
        lines = []
        for i, raw_line in enumerate(source.split('\n'), 1):
            line = raw_line.split(';')[0].strip()
            if not line:
                continue
            # INCLUDE directive
            m = re.match(r'INCLUDE\s+"([^"]+)"', line, re.IGNORECASE)
            if m:
                inc_path = os.path.join(base_dir, m.group(1))
                if os.path.exists(inc_path):
                    with open(inc_path) as f:
                        inc_lines = self.preprocess(f.read(), os.path.dirname(inc_path))
                        lines.extend(inc_lines)
                else:
                    self.error(i, f"Include file not found: {inc_path}")
                continue
            lines.append((i, line))
        return lines

    def pass1(self, lines):
        """First pass: collect labels and compute addresses."""
        self.pc = 0x150  # Default start after header
        for line_num, line in lines:
            # SECTION directive
            m = re.match(r'SECTION\s+"[^"]*"\s*,\s*ROM[0X]\s*\[\s*(\$[0-9A-Fa-f]+)\s*\]', line, re.IGNORECASE)
            if m:
                self.pc = parse_number(m.group(1))
                continue
            m = re.match(r'SECTION\s+"[^"]*"\s*,\s*ROM[0X]', line, re.IGNORECASE)
            if m:
                continue

            # EQU constant
            m = re.match(r'(\w+)\s+EQU\s+(.+)', line, re.IGNORECASE)
            if m:
                name = m.group(1)
                val = parse_number(m.group(2).strip())
                if val is not None:
                    self.constants[name] = val
                else:
                    ref = m.group(2).strip()
                    if ref in self.constants:
                        self.constants[name] = self.constants[ref]
                continue

            # Label
            m = re.match(r'(\.?\w+)\s*:', line)
            if m:
                label = m.group(1)
                if label.startswith('.'):
                    full = self.current_global_label + label
                    self.labels[full] = self.pc
                    self.log(f"Local label {full} = ${self.pc:04X}")
                else:
                    self.current_global_label = label
                    self.labels[label] = self.pc
                    self.log(f"Label {label} = ${self.pc:04X}")
                rest = line[m.end():].strip()
                if rest:
                    self.pc += self._instruction_size(rest, line_num)
                continue

            # Instruction or data directive
            self.pc += self._instruction_size(line, line_num)

    def _instruction_size(self, line, line_num):
        """Estimate instruction size for pass 1."""
        upper = line.upper().strip()

        # Data directives
        if upper.startswith('DB '):
            parts = self._parse_db_args(line[3:])
            return len(parts)
        if upper.startswith('DW '):
            return 2 * len([x.strip() for x in line[3:].split(',') if x.strip()])
        m = re.match(r'DS\s+(\S+)', upper)
        if m:
            val = parse_number(m.group(1))
            return val if val else 0

        # Single byte instructions
        mnemonic = upper.split()[0] if upper else ""
        one_byte = {'NOP', 'HALT', 'STOP', 'DI', 'EI', 'CCF', 'SCF', 'CPL', 'DAA',
                     'RLCA', 'RRCA', 'RLA', 'RRA', 'RET', 'RETI'}
        if mnemonic in one_byte:
            return 1
        if mnemonic == 'RET' and len(upper.split()) > 1:
            return 1  # RET cc

        # Push/Pop, INC/DEC r, LD r,r, ALU r
        if mnemonic in ('PUSH', 'POP'):
            return 1
        
        # CB prefix instructions
        if mnemonic in ('RLC', 'RRC', 'RL', 'RR', 'SLA', 'SRA', 'SRL', 'SWAP', 'BIT', 'RES', 'SET'):
            return 2

        # RST
        if mnemonic == 'RST':
            return 1

        # 3-byte: JP nn, JP cc nn, CALL, CALL cc, LD rr nn, LD (nn) A, LD A (nn), LD (nn) SP
        if mnemonic in ('JP', 'CALL'):
            parts = upper.split(None, 1)
            if len(parts) > 1:
                args = parts[1]
                if ',' in args:
                    return 3  # JP cc, nn or CALL cc, nn
                return 3  # JP nn or CALL nn
            return 3

        # JR is always 2 bytes
        if mnemonic == 'JR':
            return 2

        # LD is complex
        if mnemonic == 'LD':
            return self._ld_size(upper)

        # LDH
        if mnemonic == 'LDH':
            return 2

        # ADD HL, rr = 1; ADD SP, n = 2
        if mnemonic == 'ADD':
            parts = upper.split(None, 1)
            if len(parts) > 1:
                args = parts[1].split(',')
                if len(args) == 2:
                    dest = args[0].strip()
                    if dest == 'HL':
                        return 1
                    if dest == 'SP':
                        return 2
                    src = args[1].strip()
                    if src in REG8 or src == '(HL)':
                        return 1
                    return 2  # ADD A, n
            return 1

        # ALU operations: SUB/AND/OR/XOR/CP with reg=1, imm=2
        if mnemonic in ('SUB', 'AND', 'OR', 'XOR', 'CP'):
            parts = upper.split(None, 1)
            if len(parts) > 1:
                arg = parts[1].strip()
                if ',' in arg:
                    arg = arg.split(',')[1].strip()
                if arg in REG8 or arg == '(HL)':
                    return 1
                return 2
            return 1

        # ADC/SBC
        if mnemonic in ('ADC', 'SBC'):
            parts = upper.split(None, 1)
            if len(parts) > 1:
                args = parts[1].split(',')
                if len(args) == 2:
                    src = args[1].strip()
                    if src in REG8 or src == '(HL)':
                        return 1
                return 2
            return 1

        # INC/DEC
        if mnemonic in ('INC', 'DEC'):
            return 1

        return 1  # Default

    def _ld_size(self, upper):
        """Determine size of LD instruction."""
        parts = upper.split(None, 1)
        if len(parts) < 2:
            return 1
        args = parts[1].split(',', 1)
        if len(args) != 2:
            return 1
        dest = args[0].strip()
        src = args[1].strip()

        # LD r, r or LD r, (HL) or LD (HL), r
        if dest in REG8 and src in REG8:
            return 1
        # LD r, n
        if dest in REG8 and src not in REG8:
            if dest == 'A' and src.startswith('(') and src.endswith(')') and src != '(HL)' and src != '(BC)' and src != '(DE)':
                return 3  # LD A, (nn)
            if dest == 'A' and src in ('(BC)', '(DE)'):
                return 1
            return 2  # LD r, n
        # LD (HL), n
        if dest == '(HL)' and src not in REG8:
            return 2
        # LD rr, nn
        if dest in REG16:
            if src == 'HL':
                return 1  # LD SP, HL
            return 3
        # LD (nn), A or LD (nn), SP
        if dest.startswith('(') and dest.endswith(')') and dest not in ('(HL)', '(BC)', '(DE)'):
            return 3
        # LD (BC), A / LD (DE), A
        if dest in ('(BC)', '(DE)'):
            return 1
        # LD HL, SP+n
        if dest == 'HL':
            return 2
        # LDH style: LD (FF00+n), A
        if 'FF00' in dest or 'FF00' in src:
            return 2
        return 1

    def pass2(self, lines):
        """Second pass: emit actual bytes."""
        self.pc = 0x150
        self.current_global_label = ""
        for line_num, line in lines:
            # SECTION
            m = re.match(r'SECTION\s+"[^"]*"\s*,\s*ROM[0X]\s*\[\s*(\$[0-9A-Fa-f]+)\s*\]', line, re.IGNORECASE)
            if m:
                self.pc = parse_number(m.group(1))
                continue
            m = re.match(r'SECTION\s+"[^"]*"\s*,\s*ROM[0X]', line, re.IGNORECASE)
            if m:
                continue

            # EQU
            if re.match(r'\w+\s+EQU\s+', line, re.IGNORECASE):
                continue

            # Label
            m = re.match(r'(\.?\w+)\s*:', line)
            if m:
                label = m.group(1)
                if not label.startswith('.'):
                    self.current_global_label = label
                rest = line[m.end():].strip()
                if rest:
                    self._assemble_instruction(rest, line_num)
                continue

            self._assemble_instruction(line, line_num)

    def _resolve_value(self, s, line_num, is_relative=False):
        """Resolve a value that might be a number or label."""
        s = s.strip()
        num = parse_number(s)
        if num is not None:
            return num
        # Try label
        val = self.resolve_label(s)
        if val is not None:
            if is_relative:
                offset = val - (self.pc + 2)  # +2 because PC advances past the JR instruction
                if offset < -128 or offset > 127:
                    self.error(line_num, f"Relative jump out of range: {offset} (target: {s})")
                    return 0
                return offset & 0xFF
            return val
        # Check for expressions like SP+n
        m = re.match(r'SP\s*\+\s*(.+)', s, re.IGNORECASE)
        if m:
            return self._resolve_value(m.group(1), line_num) & 0xFF
        self.error(line_num, f"Unresolved symbol: {s}")
        return 0

    def _parse_db_args(self, args_str):
        """Parse DB arguments including strings."""
        result = []
        i = 0
        s = args_str.strip()
        while i < len(s):
            if s[i] == '"':
                j = s.index('"', i + 1)
                for ch in s[i+1:j]:
                    result.append(ord(ch))
                i = j + 1
            elif s[i] == ',':
                i += 1
            elif s[i] in (' ', '\t'):
                i += 1
            else:
                j = i
                while j < len(s) and s[j] not in (',', '"'):
                    j += 1
                token = s[i:j].strip()
                if token:
                    val = parse_number(token)
                    if val is not None:
                        result.append(val & 0xFF)
                    else:
                        result.append(0)
                i = j
        return result

    def _assemble_instruction(self, line, line_num):
        """Assemble a single instruction."""
        upper = line.upper().strip()
        if not upper:
            return

        # DB
        if upper.startswith('DB '):
            for b in self._parse_db_args(line[3:]):
                self.emit(b)
            return
        # DW
        if upper.startswith('DW '):
            for part in line[3:].split(','):
                val = self._resolve_value(part.strip(), line_num)
                self.emit16(val)
            return
        # DS
        m = re.match(r'DS\s+(\S+)', upper)
        if m:
            count = self._resolve_value(m.group(1), line_num)
            for _ in range(count):
                self.emit(0)
            return

        parts = upper.split(None, 1)
        mnemonic = parts[0]
        args_str = parts[1] if len(parts) > 1 else ""
        args = [a.strip() for a in args_str.split(',') if a.strip()] if args_str else []

        # --- Single byte instructions ---
        simple = {
            'NOP': 0x00, 'HALT': 0x76, 'DI': 0xF3, 'EI': 0xFB,
            'CCF': 0x3F, 'SCF': 0x37, 'CPL': 0x2F, 'DAA': 0x27,
            'RLCA': 0x07, 'RRCA': 0x0F, 'RLA': 0x17, 'RRA': 0x1F,
            'RETI': 0xD9,
        }
        if mnemonic in simple:
            self.emit(simple[mnemonic])
            return
        if mnemonic == 'STOP':
            self.emit(0x10, 0x00)
            return

        # RET
        if mnemonic == 'RET':
            if not args:
                self.emit(0xC9)
            else:
                cc = args[0]
                if cc in CONDITIONS:
                    self.emit(0xC0 | (CONDITIONS[cc] << 3))
                else:
                    self.error(line_num, f"Invalid condition: {cc}")
            return

        # PUSH / POP
        if mnemonic == 'PUSH' and args:
            rr = args[0]
            if rr in REG16_PUSH:
                self.emit(0xC5 | (REG16_PUSH[rr] << 4))
            else:
                self.error(line_num, f"Invalid register for PUSH: {rr}")
            return
        if mnemonic == 'POP' and args:
            rr = args[0]
            if rr in REG16_PUSH:
                self.emit(0xC1 | (REG16_PUSH[rr] << 4))
            else:
                self.error(line_num, f"Invalid register for POP: {rr}")
            return

        # RST
        if mnemonic == 'RST' and args:
            val = self._resolve_value(args[0], line_num)
            vectors = {0x00: 0xC7, 0x08: 0xCF, 0x10: 0xD7, 0x18: 0xDF,
                       0x20: 0xE7, 0x28: 0xEF, 0x30: 0xF7, 0x38: 0xFF}
            if val in vectors:
                self.emit(vectors[val])
            else:
                self.error(line_num, f"Invalid RST vector: ${val:02X}")
            return

        # INC / DEC 8-bit and 16-bit
        if mnemonic == 'INC' and args:
            r = args[0]
            if r in REG8:
                self.emit(0x04 | (REG8[r] << 3))
            elif r in REG16:
                self.emit(0x03 | (REG16[r] << 4))
            else:
                self.error(line_num, f"Invalid register for INC: {r}")
            return
        if mnemonic == 'DEC' and args:
            r = args[0]
            if r in REG8:
                self.emit(0x05 | (REG8[r] << 3))
            elif r in REG16:
                self.emit(0x0B | (REG16[r] << 4))
            else:
                self.error(line_num, f"Invalid register for DEC: {r}")
            return

        # JP
        if mnemonic == 'JP':
            if len(args) == 1:
                if args[0] == '(HL)' or args[0] == 'HL':
                    self.emit(0xE9)
                else:
                    self.emit(0xC3)
                    val = self._resolve_value(args[0], line_num)
                    self.emit16(val)
            elif len(args) == 2:
                cc = args[0]
                if cc in CONDITIONS:
                    self.emit(0xC2 | (CONDITIONS[cc] << 3))
                    val = self._resolve_value(args[1], line_num)
                    self.emit16(val)
                else:
                    self.error(line_num, f"Invalid condition: {cc}")
            return

        # JR
        if mnemonic == 'JR':
            if len(args) == 1:
                self.emit(0x18)
                val = self._resolve_value(args[0], line_num, is_relative=True)
                self.emit(val)
            elif len(args) == 2:
                cc = args[0]
                jr_cc = {'NZ': 0x20, 'Z': 0x28, 'NC': 0x30, 'C': 0x38}
                if cc in jr_cc:
                    self.emit(jr_cc[cc])
                    val = self._resolve_value(args[1], line_num, is_relative=True)
                    self.emit(val)
                else:
                    self.error(line_num, f"Invalid condition for JR: {cc}")
            return

        # CALL
        if mnemonic == 'CALL':
            if len(args) == 1:
                self.emit(0xCD)
                val = self._resolve_value(args[0], line_num)
                self.emit16(val)
            elif len(args) == 2:
                cc = args[0]
                if cc in CONDITIONS:
                    self.emit(0xC4 | (CONDITIONS[cc] << 3))
                    val = self._resolve_value(args[1], line_num)
                    self.emit16(val)
            return

        # LDH
        if mnemonic == 'LDH':
            if len(args) == 2:
                if args[0] == 'A':
                    # LDH A, (n) -> F0 nn
                    val = self._resolve_value(args[1].strip('()'), line_num)
                    self.emit(0xF0, val & 0xFF)
                else:
                    # LDH (n), A -> E0 nn
                    val = self._resolve_value(args[0].strip('()'), line_num)
                    self.emit(0xE0, val & 0xFF)
            return

        # LD
        if mnemonic == 'LD':
            self._assemble_ld(args, line_num, args_str)
            return

        # ADD
        if mnemonic == 'ADD':
            if len(args) == 2:
                if args[0] == 'HL':
                    rr = args[1]
                    if rr in REG16:
                        self.emit(0x09 | (REG16[rr] << 4))
                    return
                if args[0] == 'SP':
                    val = self._resolve_value(args[1], line_num)
                    self.emit(0xE8, val & 0xFF)
                    return
                if args[0] == 'A':
                    src = args[1]
                    if src in REG8:
                        self.emit(0x80 | REG8[src])
                    else:
                        val = self._resolve_value(src, line_num)
                        self.emit(0xC6, val & 0xFF)
                    return
            if len(args) == 1:
                src = args[0]
                if src in REG8:
                    self.emit(0x80 | REG8[src])
                else:
                    val = self._resolve_value(src, line_num)
                    self.emit(0xC6, val & 0xFF)
                return
            return

        # ADC
        if mnemonic == 'ADC':
            src = args[-1] if args else 'A'
            if src in REG8:
                self.emit(0x88 | REG8[src])
            else:
                val = self._resolve_value(src, line_num)
                self.emit(0xCE, val & 0xFF)
            return

        # SUB
        if mnemonic == 'SUB':
            src = args[-1] if args else 'A'
            if src in REG8:
                self.emit(0x90 | REG8[src])
            else:
                val = self._resolve_value(src, line_num)
                self.emit(0xD6, val & 0xFF)
            return

        # SBC
        if mnemonic == 'SBC':
            src = args[-1] if args else 'A'
            if src in REG8:
                self.emit(0x98 | REG8[src])
            else:
                val = self._resolve_value(src, line_num)
                self.emit(0xDE, val & 0xFF)
            return

        # AND/OR/XOR/CP
        alu_ops = {'AND': (0xA0, 0xE6), 'OR': (0xB0, 0xF6), 'XOR': (0xA8, 0xEE), 'CP': (0xB8, 0xFE)}
        if mnemonic in alu_ops:
            base_r, base_n = alu_ops[mnemonic]
            src = args[-1] if args else 'A'
            if src in REG8:
                self.emit(base_r | REG8[src])
            else:
                val = self._resolve_value(src, line_num)
                self.emit(base_n, val & 0xFF)
            return

        # CB prefix: RLC/RRC/RL/RR/SLA/SRA/SRL/SWAP
        cb_ops = {'RLC': 0x00, 'RRC': 0x08, 'RL': 0x10, 'RR': 0x18,
                  'SLA': 0x20, 'SRA': 0x28, 'SWAP': 0x30, 'SRL': 0x38}
        if mnemonic in cb_ops and args:
            r = args[0]
            if r in REG8:
                self.emit(0xCB, cb_ops[mnemonic] | REG8[r])
            else:
                self.error(line_num, f"Invalid register for {mnemonic}: {r}")
            return

        # BIT/RES/SET
        if mnemonic in ('BIT', 'RES', 'SET') and len(args) == 2:
            bit = self._resolve_value(args[0], line_num)
            r = args[1]
            base = {'BIT': 0x40, 'RES': 0x80, 'SET': 0xC0}[mnemonic]
            if r in REG8 and 0 <= bit <= 7:
                self.emit(0xCB, base | (bit << 3) | REG8[r])
            else:
                self.error(line_num, f"Invalid args for {mnemonic}: bit={bit}, reg={r}")
            return

        self.error(line_num, f"Unknown instruction: {line}")

    def _assemble_ld(self, args, line_num, raw_args):
        """Assemble LD instruction variants."""
        if len(args) != 2:
            self.error(line_num, f"LD requires 2 arguments, got {len(args)}")
            return
        dest, src = args[0], args[1]

        # LD r, r  or LD r, (HL) or LD (HL), r
        if dest in REG8 and src in REG8:
            self.emit(0x40 | (REG8[dest] << 3) | REG8[src])
            return

        # LD r, n (immediate)
        if dest in REG8 and src not in REG8:
            # Check for LD A, (BC) / LD A, (DE)
            if dest == 'A' and src == '(BC)':
                self.emit(0x0A)
                return
            if dest == 'A' and src == '(DE)':
                self.emit(0x1A)
                return
            # LD A, (nn)
            if dest == 'A' and src.startswith('(') and src.endswith(')'):
                inner = src[1:-1].strip()
                # Check for FF00+n
                m = re.match(r'FF00\s*\+\s*(.+)', inner, re.IGNORECASE)
                if m:
                    if m.group(1).strip() == 'C':
                        self.emit(0xF2)
                    else:
                        val = self._resolve_value(m.group(1), line_num)
                        self.emit(0xF0, val & 0xFF)
                    return
                val = self._resolve_value(inner, line_num)
                self.emit(0xFA)
                self.emit16(val)
                return
            # LD r, n
            val = self._resolve_value(src, line_num)
            self.emit(0x06 | (REG8[dest] << 3), val & 0xFF)
            return

        # LD (HL), n
        if dest == '(HL)' and src not in REG8:
            val = self._resolve_value(src, line_num)
            self.emit(0x36, val & 0xFF)
            return

        # LD (BC), A / LD (DE), A
        if dest == '(BC)' and src == 'A':
            self.emit(0x02)
            return
        if dest == '(DE)' and src == 'A':
            self.emit(0x12)
            return

        # LD (nn), A
        if dest.startswith('(') and dest.endswith(')') and src == 'A':
            inner = dest[1:-1].strip()
            m = re.match(r'FF00\s*\+\s*(.+)', inner, re.IGNORECASE)
            if m:
                if m.group(1).strip() == 'C':
                    self.emit(0xE2)
                else:
                    val = self._resolve_value(m.group(1), line_num)
                    self.emit(0xE0, val & 0xFF)
                return
            val = self._resolve_value(inner, line_num)
            self.emit(0xEA)
            self.emit16(val)
            return

        # LD (nn), SP
        if dest.startswith('(') and dest.endswith(')') and src == 'SP':
            inner = dest[1:-1].strip()
            val = self._resolve_value(inner, line_num)
            self.emit(0x08)
            self.emit16(val)
            return

        # LD rr, nn (16-bit immediate load)
        if dest in REG16:
            if src == 'HL' and dest == 'SP':
                self.emit(0xF9)
                return
            # Check for LD HL, SP+n
            m_sp = re.match(r'SP\s*\+\s*(.+)', src, re.IGNORECASE)
            if m_sp and dest == 'HL':
                val = self._resolve_value(m_sp.group(1), line_num)
                self.emit(0xF8, val & 0xFF)
                return
            val = self._resolve_value(src, line_num)
            self.emit(0x01 | (REG16[dest] << 4))
            self.emit16(val)
            return

        # LD (HL+), A / LD (HL-), A / LD A, (HL+) / LD A, (HL-)
        if dest == '(HLI)' or dest == '(HL+)':
            self.emit(0x22)  # LD (HL+), A
            return
        if dest == '(HLD)' or dest == '(HL-)':
            self.emit(0x32)  # LD (HL-), A
            return
        if src == '(HLI)' or src == '(HL+)':
            self.emit(0x2A)  # LD A, (HL+)
            return
        if src == '(HLD)' or src == '(HL-)':
            self.emit(0x3A)  # LD A, (HL-)
            return

        self.error(line_num, f"Unsupported LD variant: LD {dest}, {src}")

    def build_header(self):
        """Build the ROM header at 0x0100-0x014F."""
        # Entry point: NOP + JP $0150
        self.output[0x100] = 0x00  # NOP
        self.output[0x101] = 0xC3  # JP
        self.output[0x102] = 0x50  # low byte
        self.output[0x103] = 0x01  # high byte

        # Nintendo logo
        for i, b in enumerate(NINTENDO_LOGO):
            self.output[0x104 + i] = b

        # Title
        title_bytes = self.title.encode('ascii')[:15]
        for i in range(15):
            if i < len(title_bytes):
                self.output[0x134 + i] = title_bytes[i]
            else:
                self.output[0x134 + i] = 0

        # Cartridge type
        self.output[0x147] = MBC_TYPES.get(self.mbc, 0x00)

        # ROM size
        rom_kb = len(self.output) // 1024
        self.output[0x148] = ROM_SIZES.get(rom_kb, 0)

        # RAM size (0 for ROM only)
        self.output[0x149] = 0x00

        # Destination code (non-Japanese)
        self.output[0x14A] = 0x01

        # Header checksum
        checksum = 0
        for i in range(0x134, 0x14D):
            checksum = (checksum - self.output[i] - 1) & 0xFF
        self.output[0x14D] = checksum

        # Global checksum
        total = 0
        for i in range(len(self.output)):
            if i != 0x14E and i != 0x14F:
                total = (total + self.output[i]) & 0xFFFF
        self.output[0x14E] = (total >> 8) & 0xFF
        self.output[0x14F] = total & 0xFF

    def assemble(self, source, base_dir="."):
        """Full two-pass assembly."""
        lines = self.preprocess(source, base_dir)
        self.lines = lines

        # Pass 1: collect labels
        self.pass1(lines)
        self.log(f"Pass 1 complete: {len(self.labels)} labels, {len(self.constants)} constants")

        if self.errors:
            return False

        # Pass 2: emit code
        self.pass2(lines)
        self.log(f"Pass 2 complete: {self.pc} bytes used")

        if self.errors:
            return False

        # Build header
        self.build_header()

        # Pad to 32KB minimum
        while len(self.output) < 32768:
            self.output.append(0)

        return True

    def get_rom(self):
        return bytes(self.output)


def main():
    parser = argparse.ArgumentParser(description='Game Boy ROM Assembler')
    parser.add_argument('input', nargs='?', help='Input assembly file')
    parser.add_argument('-o', '--output', help='Output .gb ROM file')
    parser.add_argument('--title', default='GAME', help='ROM title (max 15 chars)')
    parser.add_argument('--mbc', default='ROM', choices=list(MBC_TYPES.keys()), help='MBC type')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--validate', action='store_true', help='Validate only, do not write')
    parser.add_argument('--tile', help='Convert tile string to 2bpp hex (comma-separated 8-char rows)')
    args = parser.parse_args()

    if args.tile:
        rows = args.tile.split(',')
        if len(rows) != 8:
            print(f"Error: tile needs 8 rows, got {len(rows)}")
            sys.exit(1)
        data = tile_to_2bpp(rows)
        print("DB " + ", ".join(f"${b:02X}" for b in data))
        return

    if not args.input:
        parser.print_help()
        sys.exit(1)

    with open(args.input) as f:
        source = f.read()

    asm = Assembler(title=args.title, mbc=args.mbc, verbose=args.verbose)
    success = asm.assemble(source, os.path.dirname(os.path.abspath(args.input)))

    for w in asm.warnings:
        print(f"⚠ {w}")
    for e in asm.errors:
        print(f"✗ {e}")

    if not success:
        print(f"\nAssembly failed with {len(asm.errors)} error(s)")
        sys.exit(1)

    rom = asm.get_rom()
    print(f"✓ Assembly successful: {len(rom)} bytes ({len(rom)//1024}KB)")
    print(f"  Title: {asm.title}")
    print(f"  Labels: {len(asm.labels)}")
    print(f"  MBC: {asm.mbc}")

    if args.validate:
        print("  (validate only — no file written)")
        return

    output_path = args.output or args.input.rsplit('.', 1)[0] + '.gb'
    with open(output_path, 'wb') as f:
        f.write(rom)
    print(f"  Written to: {output_path}")


if __name__ == '__main__':
    main()
