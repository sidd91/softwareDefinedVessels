# Message to the organizers (sent)

Drafted Sat 11:43 PDT by Claude Opus 5.5 on behalf of Logan Walker (GhostWalka). Logan sent it as below
(WORKLOG DEC-49, Sat 12:31 PDT). As he relayed the answers: the questions are fine and there is some
flexibility; there is no organizer simulator, so ArgOS runs its own (DEC-49). The memo question became
DEC-50 and the minute-12 question is Siddharth's to decide (DEC-51). Open fallbacks are in
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) #37 to #41; the AI list's source and date go in
[SOFTWARE_LOG.md](SOFTWARE_LOG.md) once known.

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

---

## Follow-up on question 5 (draft, not sent)

Drafted Sat 12:43 PDT by Claude Opus 5.5 for whoever asks again (minute 12 is Siddharth's call, DEC-51).
It names both readings, as the design freeze review asked (F4). Since question 5 was sent, the minute-19
event is labelled INJECTED, not "added".

> On minute 12 of Scenario B, we see two readings and would like to know which you intend.
> **(a)** The survey vehicle is still at sea on its own battery, as the minute-8 story implies (it holds
> depth, or waits to be recovered over the ramp until the drone has landed). After the genset trip the
> load fits the ~100 kW reserve: 48 kW with survey primary, 81 kW with rescue primary. Our governor shows
> its shedding ladder armed, first step the comms node to its 8 kW low-power mode, with no step executed,
> and runs a full sequence at a labelled, injected chilled-water pump failure at minute 19.
> **(b)** The survey vehicle is charging at 25 kW, as in Annex B's one-genset-down sum (G5 + G4 + G3
> charging = 105 kW against ~100). Then steps execute at minute 12, but the vehicle must already be on
> its cradle, so it is not surveying at minute 8 and the minute-8 conflict with the drone does not arise.
> Is (a) acceptable, or must steps execute at minute 12?
