# University Timetable Generator

Projekt generuje velka dummy data pro univerzitu a nad nimi stavi rozvrh pomoci OR-Tools CP-SAT.

Co script dela:

- generuje 8 studijnich programu po 3 rocnicich
- vytvari ucitele s rozvrhovymi omezenimi
- vytvari predmety s prednaskami a cvicenimi v rezimu kazdy tyden / liche tydny / sude tydny
- vytvari 8 velkych poslucharen a desitky dalsich specializovanych uceben
- optimalizuje hlavne pocet dni, kdy jsou ucitele ve skole
- jako vedlejsi cil zohlednuje kompaktnost rozvrhu studentskych skupin
- exportuje konkretni rozvrhy do JSON a HTML
- kazdy beh uklada vystupy do nove timestamp slozky pod `outputs`

Spusteni:

```bash
python main.py demo
```

Pouzitelne prikazy:

```bash
python main.py demo --time-limit 300
python main.py generate-data --output outputs/university_dataset.json
python main.py solve --data outputs/university_dataset.json --output-dir outputs
```

Hlavni vystupy:

- `outputs/YYYYMMDD_HHMMSS/university_dataset.json`
- `outputs/YYYYMMDD_HHMMSS/schedule.json`
- `outputs/YYYYMMDD_HHMMSS/summary.md`
- `outputs/YYYYMMDD_HHMMSS/teacher_timetables.html`
- `outputs/YYYYMMDD_HHMMSS/subject_timetables.html`
- `outputs/YYYYMMDD_HHMMSS/cohort_timetables.html`
- `outputs/YYYYMMDD_HHMMSS/room_timetables.html`
