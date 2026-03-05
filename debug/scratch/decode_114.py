import struct

hex_val = "0000000000001040"
val = struct.unpack('<d', bytes.fromhex(hex_val))[0]
print(f"Hex {hex_val} as Double: {val}")

hex_val2 = "0000000000001840"
val2 = struct.unpack('<d', bytes.fromhex(hex_val2))[0]
print(f"Hex {hex_val2} as Double: {val2}")

# Let's decode the block properly now
hex_block = "00000040bed84070000000010000000771000000080000000000000040bed84072000000080000000000000000001040"
data = bytes.fromhex(hex_block)
# Search for Tags
# Tag 112 (0x70)
# Tag 113 (0x71)
# Tag 114 (0x72)
offset = 0
while offset < len(data) - 8:
    tag = struct.unpack('<I', data[offset:offset+4])[0]
    length = struct.unpack('<I', data[offset+4:offset+8])[0]
    val_start = offset + 8
    val_end = val_start + length
    if val_end > len(data): break
    val_bytes = data[val_start:val_end]
    disp = ""
    if length == 8: disp = f"Double: {struct.unpack('<d', val_bytes)[0]}"
    print(f"Tag {tag} | Len {length} | {disp}")
    offset = val_end
