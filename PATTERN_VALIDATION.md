# Pattern-Based Validation

## ภาพรวม

ระบบใช้ **Pattern-Based Validation** เพื่อให้การตรวจสอบและให้คะแนนผลลัพธ์ OCR แม่นยำขึ้น โดยกำหนดรูปแบบของแต่ละส่วนอย่างชัดเจน

## รูปแบบ (Pattern Format)

```
[Prefix:1]-[Country/Region:1-2]-[Code/Type:2-4]-[Serial/ID:7-10]
```

### ตัวอย่าง
- `B-C-5U5-R4091534`
- `B-F-GTX-S17893848`
- `A-US-12AB-T9876543`

## รายละเอียดแต่ละส่วน

### Part 1: Prefix (คำนำหน้า)
- **ความยาว**: 1 ตัวอักษร
- **รูปแบบ**: ภาษาอังกฤษเท่านั้น (A-Z)
- **ตัวอย่าง**: `B`, `A`, `C`
- **คะแนน**: +30 ถ้าถูกต้อง, -20 ถ้าไม่ถูกต้อง

### Part 2: Country/Region (รหัสประเทศ/ภูมิภาค)
- **ความยาว**: 1-2 ตัวอักษร
- **รูปแบบ**: ภาษาอังกฤษเท่านั้น (A-Z)
- **ตัวอย่าง**: `C`, `F`, `US`, `TH`
- **คะแนน**: +30 ถ้าถูกต้อง, -20 ถ้าไม่ถูกต้อง

### Part 3: Code/Type (รหัสประเภท)
- **ความยาว**: 2-4 ตัวอักษร
- **รูปแบบ**: ภาษาอังกฤษและตัวเลข (A-Z, 0-9)
- **ตัวอย่าง**: `5U5`, `GTX`, `12AB`, `A1B2`
- **คะแนน**: +30 ถ้าถูกต้อง, -20 ถ้าไม่ถูกต้อง

### Part 4: Serial/ID (หมายเลขซีเรียล)
- **ความยาว**: 7-10 ตัวอักษร
- **รูปแบบ**: ภาษาอังกฤษและตัวเลข (A-Z, 0-9)
- **รูปแบบที่ดีที่สุด**: 1 ตัวอักษร + 7-8 ตัวเลข (เช่น `R4091534`)
- **คะแนน**: 
  - +40 สำหรับความยาวถูกต้อง
  - +50 สำหรับรูปแบบที่สมบูรณ์แบบ (1 ตัวอักษร + 7-8 ตัวเลข)
  - +30 สำหรับรูปแบบที่ดี (มีตัวเลข >= 7 ตัว)
  - +10 สำหรับรูปแบบที่ยอมรับได้ (มีตัวเลข >= 6 ตัว)
  - -10 ถ้ามีตัวเลขน้อยเกินไป
  - -30 ถ้าความยาวไม่ถูกต้อง
  - -15 ต่อตัวอักษรสำหรับ noise (เช่น เว้นวรรค + ตัวอักษร/ตัวเลขเดี่ยว)

## ระบบให้คะแนน

### คะแนนพื้นฐาน
- **โครงสร้างถูกต้อง**: +60 (มี 4 ส่วนแยกด้วย `-`)

### คะแนนรวมสูงสุด
- โครงสร้างถูกต้อง: 60
- Prefix ถูกต้อง: 30
- Country ถูกต้อง: 30
- Code ถูกต้อง: 30
- Serial ถูกต้อง: 40
- Serial รูปแบบสมบูรณ์แบบ: 50
- **รวม**: 240 คะแนน

### ตัวอย่างการให้คะแนน

#### ตัวอย่าง 1: รูปแบบสมบูรณ์แบบ
```
Input: "B-C-5U5-R4091534"

✓ Prefix 'B' valid (1 letter) → +30
✓ Country 'C' valid (1 letter) → +30
✓ Code '5U5' valid (3 chars) → +30
✓ Serial 'R4091534' valid (9 chars: 1 letter, 8 digits) → +40
★ PERFECT Serial format (1 letter + 8 digits) → +50

Total: 60 + 30 + 30 + 30 + 40 + 50 = 240
```

#### ตัวอย่าง 2: มี Noise
```
Input: "B-C-5U5-R4091534 9"

✓ Prefix 'B' valid → +30
✓ Country 'C' valid → +30
✓ Code '5U5' valid → +30
✓ Serial 'R40915349' valid (after cleanup) → +40
★ PERFECT format → +50
⚠ Trailing noise detected: ' 9' (penalty: -15) → -15

Total: 60 + 30 + 30 + 30 + 40 + 50 - 15 = 225
```

#### ตัวอย่าง 3: รูปแบบไม่ถูกต้อง
```
Input: "BB-C-5U5-R4091534"

✗ Prefix 'BB' invalid (expected 1 letter) → -20
✓ Country 'C' valid → +30
✓ Code '5U5' valid → +30
✓ Serial valid → +40
★ PERFECT format → +50

Total: 60 - 20 + 30 + 30 + 40 + 50 = 190
```

## การเปรียบเทียบกับ Multi-Page Results

เมื่ออ่านหลายหน้า ระบบจะใช้ **Combined Scoring**:

```
Combined Score = 
    (Average Score × 0.4) +
    (Max Score × 0.2) +
    (Frequency Ratio × 100 × 0.3) +
    (Page Count × 10 × 0.1) +
    (Penalty for Noise)
```

### ตัวอย่าง
```
Page 1: "B-C-5U5-R4091534 9" (score: 225, freq: 1/8)
Page 2: "B-C-5U5-R4091534"   (score: 240, freq: 7/7)

Result 1:
- Avg: 225, Max: 225, Freq: 0.125, Pages: 1
- Combined: (225×0.4) + (225×0.2) + (12.5×0.3) + (10×0.1) - 30 = 106.75

Result 2:
- Avg: 240, Max: 240, Freq: 1.0, Pages: 1
- Combined: (240×0.4) + (240×0.2) + (100×0.3) + (10×0.1) = 175

✅ Winner: "B-C-5U5-R4091534" (score: 175)
```

## การตั้งค่าใน config.ini

```ini
# เปิด/ปิด Pattern Validation
enable_pattern_validation = True

# กำหนดความยาวของแต่ละส่วน
pattern_prefix_length = 1      # Prefix: 1 ตัวอักษร
pattern_country_min = 1        # Country: ขั้นต่ำ 1 ตัวอักษร
pattern_country_max = 2        # Country: สูงสุด 2 ตัวอักษร
pattern_code_min = 2           # Code: ขั้นต่ำ 2 ตัวอักษร
pattern_code_max = 4           # Code: สูงสุด 4 ตัวอักษร
pattern_serial_min = 7         # Serial: ขั้นต่ำ 7 ตัวอักษร
pattern_serial_max = 10        # Serial: สูงสุด 10 ตัวอักษร
```

## ข้อดีของ Pattern Validation

1. **แม่นยำสูงขึ้น**: ตรวจสอบแต่ละส่วนอย่างละเอียด
2. **ระบุ Noise ได้**: ตรวจจับตัวอักษร/ตัวเลขเดี่ยวที่ติดมาจาก OCR
3. **ยืดหยุ่น**: สามารถปรับความยาวแต่ละส่วนได้จาก config
4. **Log ละเอียด**: แสดงการตรวจสอบแต่ละส่วนใน log
5. **รองรับหลายหน้า**: รวมผลจากหลายหน้าอย่างชาญฉลาด

## ตัวอย่าง Log Output

```
[PATTERN] ✓ Prefix 'B' valid (1 letter)
[PATTERN] ✓ Country 'C' valid (1 letter)
[PATTERN] ✓ Code '5U5' valid (3 char(s))
[PATTERN] ✓ Serial 'R4091534' valid (9 chars: 1 letter(s), 8 digit(s))
[PATTERN] ★ PERFECT Serial format (1 letter + 8 digits)
[PATTERN] Total score: 240 for 'B-C-5U5-R4091534'
```

## การปิดใช้งาน

หากต้องการใช้ validation แบบเดิม ให้ตั้งค่าใน config.ini:

```ini
enable_pattern_validation = False
```

ระบบจะกลับไปใช้วิธีการตรวจสอบแบบเดิม
