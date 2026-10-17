# Message to the organizers (draft, not sent)

Drafted Sat 11:43 PDT by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka), for Logan to send if he
chooses. Nothing has been sent. Record each answer in WORKLOG; the AI list's source and date also go in
[SOFTWARE_LOG.md](SOFTWARE_LOG.md). The fallback for each question, if no answer comes, is in
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) #37 to #41.

---

Hello, five short questions on the Fincantieri Software Defined Vessel challenge:

1. **Submission.** What do we submit, where, and by when: a repository link (which branch, tag or
   commit), the PDFs, a form or portal? Our repository is private on GitHub. Should we make it public,
   or give the jury access another way?
2. **Simulator.** Slide 13 says "Deterministic simulation provided". Is there an organizer simulator we
   should run against, and where do we get it? If not, we use our own seeded simulator, as the brief
   describes.
3. **AI services.** The Data Use Authorization allows AI services only from the authorized list
   published before Day 0. Can you confirm that Claude (Anthropic) is on it, and tell us where the list
   is published?
4. **Memo.** The brief asks for a Scenario C design memo of at most 2 pages on one implicit crew rule.
   Slide 14 describes a 2-page design memo on architectural logic and constraint handling. Is that the
   same document, or do you also want an architecture memo?
5. **Scenario B, minute 12.** We run G3, G4 and G5, because G2 to G5 together exceed the 10 t mass
   margin. At minute 12 the survey vehicle is on its own battery, so the brief's 105 kW case does not
   arise: after the genset trip the load still fits, and our governor shows its shedding ladder armed
   with no steps executed. It executes a full shedding sequence at a clearly labelled added event, a
   chilled-water pump failure at minute 19. Is that acceptable, or must steps execute at minute 12?

Thank you,
Logan Walker (team with Siddharth Chawla)
