# University Timetable Generator

Generátor a editor univerzitních rozvrhů nad `OR-Tools CP-SAT`.

Projekt umí:

- vygenerovat ukázková univerzitní data,
- spočítat rozvrh do `schedule.json`,
- vyrenderovat HTML přehledy pro učitele, předměty, ročníky a místnosti,
- ručně upravovat rozvrh přes webové rozhraní,
- po ručních změnách zkontrolovat kolize učitelů, místností a překryvy přednášek s cvičeními.

README je psané tak, aby podle něj šel projekt:

- spustit od nuly,
- používat s dummy daty,
- naplnit vlastními daty,
- bezpečně zkontrolovat po ručních úpravách.

## 1. Požadavky

- Python `3.12+`
- Windows / PowerShell je v projektu primární prostředí, ale projekt je čistý Python
- závislost `ortools`

Instalace:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Pokud už používáš existující virtuální prostředí:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. Struktura projektu

Hlavní soubory:

- `main.py`
  Vstupní CLI.
- `timetable/data.py`
  Generátor demo datasetu.
- `timetable/solver.py`
  Optimalizační model a výpočet rozvrhu.
- `timetable/render.py`
  Render HTML a textových výstupů.
- `timetable/editor.py`
  Logika ručních změn ve webovém editoru.
- `timetable/server.py`
  Lokální HTTP server pro editor.
- `timetable/final_control.py`
  Finální kontrola konfliktů.
- `timetable/models.py`
  Datové modely a JSON formáty.

Výstupy běhů:

- `outputs/YYYYMMDD_HHMMSS/university_dataset.json`
- `outputs/YYYYMMDD_HHMMSS/schedule.json`
- `outputs/YYYYMMDD_HHMMSS/summary.md`
- `outputs/YYYYMMDD_HHMMSS/teacher_timetables.html`
- `outputs/YYYYMMDD_HHMMSS/subject_timetables.html`
- `outputs/YYYYMMDD_HHMMSS/cohort_timetables.html`
- `outputs/YYYYMMDD_HHMMSS/room_timetables.html`

Každý běh vytváří novou timestamp složku pod `outputs`.

## 3. Nejrychlejší start

Jedním příkazem vygeneruješ demo data, spočítáš rozvrh a dostaneš HTML výstupy:

```powershell
.\.venv\Scripts\python.exe main.py demo
```

Potom spustíš editor:

```powershell
.\.venv\Scripts\python.exe main.py serve
```

Výchozí adresa editoru:

```text
http://127.0.0.1:8050/teacher_timetables.html
```

## 4. CLI příkazy

### `demo`

Vygeneruje demo dataset, spočítá rozvrh, uloží HTML a JSON.

```powershell
.\.venv\Scripts\python.exe main.py demo
```

Příklad s parametry:

```powershell
.\.venv\Scripts\python.exe main.py demo --seed 17 --program-count 8 --years-per-program 3 --courses-per-year 5 --time-limit 300
```

### `generate-data`

Jen vygeneruje dataset bez řešení rozvrhu.

```powershell
.\.venv\Scripts\python.exe main.py generate-data
```

Nebo do vlastní cesty:

```powershell
.\.venv\Scripts\python.exe main.py generate-data --output outputs\my_dataset.json
```

### `solve`

Načte existující `university_dataset.json` a spočítá rozvrh.

```powershell
.\.venv\Scripts\python.exe main.py solve --data outputs\20260426_190702\university_dataset.json
```

Když `--data` nevyplníš, vezme se poslední dataset z `outputs`.

### `serve`

Spustí webový editor nad posledním nebo zadaným během.

```powershell
.\.venv\Scripts\python.exe main.py serve
```

Nad konkrétním runem:

```powershell
.\.venv\Scripts\python.exe main.py serve --run-dir outputs\20260426_190702
```

Jiný port:

```powershell
.\.venv\Scripts\python.exe main.py serve --port 8060
```

Výchozí port je `8050`.

### `final-control`

Zkontroluje, že v rozvrhu nejsou:

- kolize učitelů,
- kolize místností,
- překryv přednášky a cvičení ve stejném ročníku/cohortě.

```powershell
.\.venv\Scripts\python.exe main.py final-control
```

Nad konkrétním runem:

```powershell
.\.venv\Scripts\python.exe main.py final-control --run-dir outputs\20260426_190702
```

Úspěch vrací `0`, konflikt vrací `1`.

## 5. Webový editor

Editor funguje nad už spočítaným rozvrhem.

Postup:

1. spusť `demo` nebo `solve`,
2. spusť `serve`,
3. otevři `teacher_timetables.html`,
4. u bloku klikni na `Nastaveni`,
5. vyber:
   - týden výuky,
   - cílový slot,
   - cílovou místnost,
6. klikni na `Ulozit`.

Editor při změnách hlídá:

- nedostupnost učitele,
- kolizi učitele,
- překryv výuky v dané cohortě,
- obsazenost místnosti,
- požadované feature místnosti,
- minimální kapacitu místnosti.

V učitelském přehledu jsou červeně označené sloty z `unavailable_slot_ids`.

Po uložení se automaticky přepíše:

- `schedule.json`
- `university_dataset.json`
- všechna HTML v daném run adresáři

## 6. Jak dodat vlastní data

Pokud nechceš používat demo generátor, připrav vlastní `university_dataset.json` ve formátu popsaném níže a potom spusť:

```powershell
.\.venv\Scripts\python.exe main.py solve --data cesta\k\university_dataset.json
```

Nejjednodušší doporučený workflow:

1. vygeneruj si jednou demo dataset:

```powershell
.\.venv\Scripts\python.exe main.py generate-data
```

2. otevři vygenerovaný `outputs\...\university_dataset.json`,
3. přepiš jeho obsah svými reálnými daty,
4. spusť `solve --data ...`,
5. případné jemné úpravy udělej přes `serve`,
6. na konci spusť `final-control`.

Tohle je nejlepší cesta, protože vycházíš z přesně správné struktury.

## 7. Formát `university_dataset.json`

Kořen JSON musí obsahovat:

```json
{
  "teachers": [],
  "rooms": [],
  "cohorts": [],
  "study_groups": [],
  "courses": [],
  "meta": {}
}
```

### `teachers`

Každý učitel:

```json
{
  "id": "CS-PRO-01",
  "name": "Jan Novak",
  "department": "School of Computing",
  "subjects": ["CS-Y1-01", "CS-Y1-02"],
  "unavailable_slot_ids": [0, 1, 15],
  "preferred_day_codes": ["MON", "WED"],
  "avoid_single_block_days": true,
  "preferred_max_teaching_days": 2,
  "absolute_max_teaching_days": 3
}
```

Povinné poznámky:

- `id` musí být unikátní.
- `subjects` je seznam `course.id`, které může učit.
- `unavailable_slot_ids` jsou indexy slotů `0..34`.
- Dny jsou `MON`, `TUE`, `WED`, `THU`, `FRI`.

Mapování `slot_id`:

- `0..6` pondělí
- `7..13` úterý
- `14..20` středa
- `21..27` čtvrtek
- `28..34` pátek

Časy bloků:

- `0` `08:45-10:15`
- `1` `10:30-12:00`
- `2` `12:15-13:45`
- `3` `14:00-15:30`
- `4` `15:45-17:15`
- `5` `17:30-19:00`
- `6` `19:15-20:45`

### `rooms`

Každá místnost:

```json
{
  "id": "CL-01",
  "name": "Computer Lab 1",
  "capacity": 28,
  "building": "Digital Center",
  "features": ["computer_lab"]
}
```

Povinné poznámky:

- `id` musí být unikátní.
- `capacity` musí odpovídat reálnému maximu.
- `features` je seznam schopností místnosti, například:
  - `lecture_hall`
  - `seminar_room`
  - `computer_lab`
  - `project_room`
  - `electronics_lab`
  - `mechanics_lab`
  - `biotech_lab`

Solver a editor respektují právě tyto feature.

### `cohorts`

Jedna cohorta = typicky konkrétní obor + ročník.

```json
{
  "id": "CS-Y1",
  "program_id": "CS",
  "program_name": "Computer Science",
  "year": 1,
  "size": 180,
  "group_count": 8
}
```

Povinné poznámky:

- `id` musí být unikátní.
- `size` je celkový počet studentů v ročníku.
- `group_count` musí odpovídat počtu skupin v `study_groups`.

### `study_groups`

Jednotlivé cvičební skupiny cohorty.

```json
{
  "id": "CS-Y1-G1",
  "cohort_id": "CS-Y1",
  "name": "CS-Y1 Group 1",
  "size": 23
}
```

Povinné poznámky:

- `id` musí být unikátní.
- `cohort_id` musí existovat v `cohorts`.
- součet velikostí skupin by měl odpovídat `cohort.size`.

### `courses`

Každý předmět:

```json
{
  "id": "CS-Y1-01",
  "code": "CS101",
  "name": "Programming Fundamentals",
  "program_id": "CS",
  "program_name": "Computer Science",
  "year": 1,
  "cohort_id": "CS-Y1",
  "student_count": 180,
  "lecture_teacher_id": "CS-PRO-01",
  "practical_teacher_by_group": {
    "CS-Y1-G1": "CS-INS-01",
    "CS-Y1-G2": "CS-INS-02"
  },
  "lecture_room_features": ["lecture_hall"],
  "practical_room_features": ["computer_lab"],
  "lecture_blocks_per_week": 1,
  "practical_frequency": "all",
  "practical_group_size": 28
}
```

Povinné poznámky:

- `cohort_id` musí existovat.
- `lecture_teacher_id` musí existovat v `teachers`.
- každý teacher v `practical_teacher_by_group` musí existovat.
- klíče v `practical_teacher_by_group` musí být existující `study_group.id`.
- `lecture_room_features` a `practical_room_features` musí odpovídat `room.features`.
- `practical_frequency` musí být jedno z:
  - `all`
  - `odd`
  - `even`

## 8. Co přesně solver očekává

Aby solver fungoval správně, drž se těchto pravidel:

- každý `id` musí být unikátní v rámci své sekce,
- všechny reference mezi sekcemi musí ukazovat na existující záznamy,
- každá cohorta musí mít definované skupiny,
- každá session musí mít reálně dostupného učitele,
- každá lecture musí mít aspoň jednu kompatibilní místnost podle `lecture_room_features`,
- každá practical session musí mít aspoň jednu kompatibilní místnost podle `practical_room_features`,
- kapacita místností musí dávat smysl vůči `student_count` a velikostem skupin,
- pokud dáš příliš mnoho `unavailable_slot_ids`, solver může skončit jako neřešitelný.

## 9. Co vzniká v `schedule.json`

Soubor `schedule.json` je výsledný rozvrh po solveru nebo po ručních úpravách.

Každá session vypadá přibližně takto:

```json
{
  "session_id": "CS-Y1-01-LEC",
  "course_id": "CS-Y1-01",
  "course_code": "CS101",
  "course_name": "Programming Fundamentals",
  "teacher_id": "CS-PRO-01",
  "teacher_name": "Jan Novak",
  "cohort_id": "CS-Y1",
  "audience_group_ids": ["CS-Y1-G1", "CS-Y1-G2"],
  "session_kind": "lecture",
  "week_pattern": "all",
  "room_id": "LH-01",
  "room_name": "Lecture Hall 1",
  "day_code": "MON",
  "day_label": "Po",
  "start": "08:45",
  "end": "10:15",
  "slot_id": 0,
  "display_label": "CS101 lecture"
}
```

Ruční editor mění právě tento soubor.

## 10. Doporučený workflow pro reálná data

Nejbezpečnější praktický postup:

1. připrav `university_dataset.json` podle struktury výše,
2. spusť:

```powershell
.\.venv\Scripts\python.exe main.py solve --data cesta\k\university_dataset.json
```

3. otevři editor:

```powershell
.\.venv\Scripts\python.exe main.py serve --run-dir outputs\YYYYMMDD_HHMMSS
```

4. udělej ruční změny,
5. po každé větší sérii změn spusť:

```powershell
.\.venv\Scripts\python.exe main.py final-control --run-dir outputs\YYYYMMDD_HHMMSS
```

6. pokud kontrola vrátí konflikty, oprav je v editoru,
7. finální `schedule.json` ber jako export rozvrhu.

## 11. Typické chyby v datech

Nejčastější problémy:

- `teacher_id` v course neexistuje,
- skupina v `practical_teacher_by_group` neexistuje,
- `cohort.size` nesedí na skupiny,
- lecture chce `lecture_hall`, ale v datech taková místnost není,
- practical chce `computer_lab`, ale místnost má jen `seminar_room`,
- kapacita místnosti nestačí na přednášku,
- učitel je zablokovaný ve většině slotů a rozvrh pak nejde sestavit.

## 12. Testy

Spuštění testů:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_timetable
```

Testy pokrývají:

- generování dat,
- základní bezkonfliktní řešení,
- HTML render,
- ruční změny slotu,
- ruční změny týdne,
- ruční změny místnosti,
- filtraci zakázaných slotů učitele,
- filtraci obsazených místností,
- finální kontrolu validního rozvrhu.

## 13. Doporučení na závěr

Pokud budeš nahrávat vlastní data poprvé, nepiš dataset od nuly naslepo. Nejlepší je:

- nejdřív si vygenerovat demo dataset,
- ten použít jako šablonu,
- měnit jen hodnoty,
- zachovat strukturu a názvy polí přesně.

To je nejrychlejší cesta, jak se vyhnout chybám ve formátu.
