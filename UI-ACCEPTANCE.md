# Modernizarea UI/UX — criterii de acceptare

## Sistem vizual

- Identitatea păstrează bleumarinul (#182e4b); paginile folosesc fundal deschis, carduri albe și accente albastre, mov, turcoaz și portocalii.
- Culorile, spațierea, umbrele și razele sunt definite prin variabile în `frontend/src/design-system.css`. Un singur fișier de sistem vizual completează stilurile de structură; temele intermediare sunt eliminate.
- Butoanele au stări hover, active, focus și disabled. Tranzițiile respectă `prefers-reduced-motion`.

## Participare

- Hero cu titlu, mesaj și acțiuni funcționale către concursuri și explicația participării.
- Cardurile edițiilor afișează numele concursului, ediția, statusul, întrebările, participanții și acțiunea disponibilă, folosind datele API existente.
- Filtrele Toate / Înscrieri deschise / Programate / Finalizate funcționează, inclusiv starea fără rezultate și resetarea filtrului.
- Întrebările sunt lizibile; opțiunile sunt carduri mari, în două coloane pe desktop și una pe telefon. Literele și indicatorii checked completează culorile.
- Selecția primește feedback imediat. După trimitere apare confirmarea și răspunsurile sunt blocate. Corectitudinea rămâne ascunsă până la publicarea rezultatelor.
- Bara de progres are etichetă accesibilă. Pauza și conexiunea rămân vizibile. Nu se adaugă un timer: concursul existent este condus manual de administrator, fără puncte pentru viteză.
- Rezultatele disting pozițiile 1–3, participantul curent, răspunsurile corecte și răspunsurile greșite selectate.

## Administrare

- Navigație bleumarin, suprafețe deschise, statistici și carduri albe, controale live și badge-uri distincte.
- Căutarea după nume/descriere și filtrul de status se combină; lipsa rezultatelor oferă resetare.
- Crearea/editarea întrebărilor, participanții, programarea, pauza, reluarea și finalizarea rămân disponibile.

## Verificare

- Build TypeScript/Vite și testele existente trec.
- Verificare în browser la 390, 768 și 1440 px: fără derulare orizontală pe paginile principale, autentificare, ediție, administrare și stările de concurs.
- Selecția simplă/multiplă, confirmarea, blocarea la pauză/deconectare și protecția rolului ADMIN sunt acoperite de testele existente.
- Navigarea cu tastatura are focus vizibil. Culorile nu sunt singurul indicator al selecției, statusului sau corectitudinii.
- Nicio modificare de backend, autentificare, punctaj, migrare de date sau sincronizare live.

## Rezultate verificate

- `npm run build`: trecut.
- `npm test`: 7/7 teste trecute.
- Browser Chrome: pagină principală, autentificare/înregistrare, dashboard, ediția 9, control live și formular de întrebare verificate; căutarea/resetarea filtrelor și filtrarea edițiilor executate.
- Stările participantului (întrebare, așteptare, pauză, confirmare și rezultate) verificate folosind răspunsuri API de previzualizare, fără a porni sau modifica ediții reale.
- `prefers-reduced-motion: reduce`: derularea devine `auto`; animațiile și tranzițiile sunt dezactivate.
- Capturile și raportul verificării sunt salvate în `.local/ui-*`. Previzualizările nu reprezintă un test live cu mai mulți participanți reali.
