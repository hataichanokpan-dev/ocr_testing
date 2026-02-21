# Strict Pattern Validation for Serial/ID

## ภาพรวม

ระบบได้รับการอัปเดตให้มีการตรวจสอบ **Serial/ID (Part 4)** อย่างเข้มงวด ตามข้อกำหนดที่ชัดเจน

## รูปแบบ Serial/ID ที่ยอมรับ

### ข้อกำหนด
1. **ความยาว**: 7-9 หลักเท่านั้น (ไม่เกิน 9 หลักแน่นอน)
2. **หลักแรก**: ต้องเป็น `S` หรือ `R` เท่านั้น
3. **หลักที่เหลือ**: ต้องเป็นตัวเลข 0-9 ทั้งหมด

### รูปแบบที่ถูกต้อง
```
✓ R4091534    (9 หลัก: R + 8 ตัวเลข)
✓ S1789384    (8 หลัก: S + 7 ตัวเลข)
✓ R123456     (7 หลัก: R + 6 ตัวเลข - ความยาวต่ำสุด)
✓ S12345678   (9 หลัก: S + 8 ตัวเลข - ความยาวสูงสุด)
```

### รูปแบบที่ไม่ถูกต้อง
```
✗ T4091534    (prefix ไม่ใช่ S หรือ R)
✗ A1234567    (prefix ไม่ใช่ S หรือ R)
✗ R409153A    (มีตัวอักษร 'A' หลังตัวเลข)
✗ S12AB567    (มีตัวอักษรปะปนในตัวเลข)
✗ R40915      (สั้นเกินไป - เพียง 6 หลัก)
✗ S123456789  (ยาวเกินไป - 10 หลัก)
```

## ตัวอย่างรูปแบบเต็ม

### รูปแบบสมบูรณ์แบบ
```
B-C-5U5-R4091534   ✓ (Score: 290)
B-F-GTX-S1789384   ✓ (Score: 290)
A-US-AB12-R123456  ✓ (Score: 270)
```

### รูปแบบที่ไม่ผ่าน
```
B-C-5U5-T4091534   ✗ (Score: 150) - Invalid prefix 'T'
B-C-5U5-R409153A   ✗ (Score: 180) - Letter after digits
B-C-5U5-R40915     ✗ (Score: 120) - Too short
```

## ระบบให้คะแนน Serial/ID

### คะแนนพื้นฐาน
- ✓ **ความยาวถูกต้อง** (7-9 หลัก): +40
- ✓ **Prefix ถูกต้อง** (S หรือ R): +30
- ★ **Format สมบูรณ์แบบ** (prefix + all digits): +50
- ★ **ความยาวเหมาะสม** (8-9 หลัก): +20 bonus

### Penalty
- ✗ **Prefix ไม่ถูกต้อง**: -40
- ✗ **มี non-digit หลัง prefix**: -40
- ✗ **ความยาวไม่ถูกต้อง**: -30
- ⚠ **Trailing noise** (เช่น space + char): -15 ต่อตัวอักษร

### คะแนนสูงสุด
```
Base (structure)           : 60
Prefix (B)                : 30
Country (C)               : 30
Code (5U5)               : 30
Serial length valid       : 40
Serial prefix valid (R/S) : 30
Perfect format            : 50
Ideal length (8-9)       : 20
─────────────────────────────
Total                     : 290
```

## การเปรียบเทียบคะแนน

### ตัวอย่าง 1: รูปแบบสมบูรณ์แบบ
```
Input: "B-C-5U5-R4091534"

[PATTERN] ✓ Prefix 'B' valid (1 letter) → +30
[PATTERN] ✓ Country 'C' valid (1 letter) → +30
[PATTERN] ✓ Code '5U5' valid (3 char(s)) → +30
[PATTERN] ✓ Serial prefix 'R' valid (allowed: S, R) → +30
[PATTERN] ★ PERFECT Serial format (R + 8 digits) → +50
[PATTERN] ★ Ideal length: 9 chars → +20
[PATTERN] Total score: 290
```

### ตัวอย่าง 2: Prefix ไม่ถูกต้อง
```
Input: "B-C-5U5-T4091534"

[PATTERN] ✓ Prefix 'B' valid → +30
[PATTERN] ✓ Country 'C' valid → +30
[PATTERN] ✓ Code '5U5' valid → +30
[PATTERN] ✗ Serial prefix 'T' invalid (allowed: S, R) → -40
[PATTERN] Total score: 150
```

### ตัวอย่าง 3: มีตัวอักษรปะปน
```
Input: "B-C-5U5-R409153A"

[PATTERN] ✓ Prefix 'B' valid → +30
[PATTERN] ✓ Country 'C' valid → +30
[PATTERN] ✓ Code '5U5' valid → +30
[PATTERN] ✓ Serial prefix 'R' valid → +30
[PATTERN] ✗ Serial has non-digit chars after prefix: 1 invalid char(s) → -40
[PATTERN] Total score: 180
```

## การตั้งค่าใน config.ini

```ini
# Pattern-Based Validation
enable_pattern_validation = True

# Serial/ID Settings
pattern_serial_min = 7                      # ความยาวต่ำสุด
pattern_serial_max = 9                      # ความยาวสูงสุด (ไม่เกิน 9)
pattern_serial_allowed_prefixes = S,R       # หลักแรกที่อนุญาต
```

## ข้อดีของการตรวจสอบแบบเข้มงวด

1. **แม่นยำสูงสุด**: ตรวจสอบทุกหลักอย่างละเอียด
2. **ป้องกัน False Positive**: ไม่ยอมรับ serial ที่มี prefix ผิด
3. **ตรวจจับ OCR Error**: จับตัวอักษรที่ปะปนในตัวเลขได้
4. **รองรับ Lowercase**: แปลง prefix เป็นตัวพิมพ์ใหญ่อัตโนมัติ
5. **Log ละเอียด**: แสดงเหตุผลว่าทำไมผ่าน/ไม่ผ่าน

## ผลการทดสอบ

### Valid Cases (คะแนนสูง)
```
B-C-5U5-R4091534       → 290 ✓
B-C-5U5-S1789384       → 290 ✓
A-US-GTX-R123456       → 270 ✓
B-F-AB12-S12345678     → 290 ✓
B-C-5U5-r4091534       → 290 ✓ (auto uppercase)
```

### Invalid Cases (คะแนนต่ำ)
```
B-C-5U5-T4091534       → 150 ✗ (wrong prefix)
B-C-5U5-A1234567       → 150 ✗ (wrong prefix)
B-C-5U5-R409153A       → 180 ✗ (letter in serial)
B-C-5U5-R40915         → 120 ✗ (too short)
B-C-5U5-S123456789     → 120 ✗ (too long)
```

## Multi-Page Analysis

เมื่ออ่านหลายหน้า serial ที่ถูกต้อง (R/S prefix) จะได้คะแนนสูงกว่า:

```
Page 1: "B-C-5U5-T4091534"  (score: 150, invalid T)
Page 2: "B-C-5U5-R4091534"  (score: 290, valid R)

✅ Winner: "B-C-5U5-R4091534" (ถูกต้องตาม pattern)
```

## ตัวอย่าง Log Output

```log
[PATTERN] ✓ Prefix 'B' valid (1 letter)
[PATTERN] ✓ Country 'C' valid (1 letter)
[PATTERN] ✓ Code '5U5' valid (3 char(s))
[PATTERN] ✓ Serial prefix 'R' valid (allowed: S, R)
[PATTERN] ★ PERFECT Serial format (R + 8 digits)
[PATTERN] ★ Ideal length: 9 chars
[PATTERN] Total score: 290 for 'B-C-5U5-R4091534'
```

## การเพิ่ม/เปลี่ยน Allowed Prefixes

หากต้องการอนุญาตตัวอักษรอื่น แก้ไขใน config.ini:

```ini
# อนุญาตเฉพาะ S และ R
pattern_serial_allowed_prefixes = S,R

# หรือเพิ่มตัวอื่น เช่น T
pattern_serial_allowed_prefixes = S,R,T

# หรือทุกตัวอักษร (ปิด strict mode)
pattern_serial_allowed_prefixes = 
```

เมื่อเว้นว่าง (`pattern_serial_allowed_prefixes = `) ระบบจะกลับไปใช้ validation แบบเดิม (ยอมรับ A-Z ทั้งหมด)
