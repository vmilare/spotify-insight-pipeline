# Worked examples: applying the shared label definitions

Definitions: [`config/labels.yaml`](../config/labels.yaml) (the course's common labels). The labels below are the author's
hand labels on the **development** set ([`evals/dev_50_labeled.csv`](../evals/dev_50_labeled.csv)); the golden set is never used
for examples. Rule references: topic = highest-severity specific problem (first on a tie; first praised feature for
praise; general → `other`); intent precedence cancellation > complaint > request > praise > unclear; severity 1–5 by
reported impact, never by stars or anger.

| Review (dev, abridged) | Label (topic / intent / severity) | Rule applied |
|---|---|---|
| `e9a7546c` "love it but please … get rid of the smart shuffle thing … make it a separate button" | usability / complaint / 2 | Shuffle control = controls/navigation → **usability**. Praise + criticism → **complaint** (mixed counts as complaint). Annoyance, no lost function → **2**. |
| `f24cd91b` "issues with playing music and everything stops working until you restart" | playback / complaint / 4 | Playback failure → **playback**; music cannot play until restart → core task blocked → **4**. |
| `99566d17` "haven't been able to use spotify for over a month because my account … does not work" | access / complaint / 4 | Account access failure → **access**; app unusable → core task blocked → **4**. |
| `84c09d0f` "To much problem.. all the items are gone premium..." | billing / complaint / 2 | Features moved behind Premium = premium-only controls → **billing** (a plan mention alone would not be). Generic dissatisfaction → **2**. |
| `2c2fefc7` "Always great! Even the support team is amazing!" | support / praise / 1 | First *specific* praised feature is the support team → **support**; praise → severity **1**. |
| `63f6de17` "Very useful for vibing … the song keeps on [while using other apps]" | playback / praise / 1 | First specific praised feature is uninterrupted background playback → **playback**. |
| `84b770bb` "Good app. Highly recommended" | other / praise / 1 | General praise with no specific feature → **other**. |
| `8585f42d` "Boycott" | other / unclear / 2 | Bare boycott slogan with no product complaint or personal departure → **unclear**, topic **other** (labeler note: no reason given). |
| `641fcc61` Bengali text, roughly "never seen such a useless app … ban this app" | other / cancellation / 2 | Unsupported-language handling: the labeler translated it to judge; no specific product issue → **other**. Model runs do not translate; such texts are flagged `non_english_unverified`. |
| `48a33ded` "^This is the proper way to have a pay wall system. Great app …" | billing / praise / 1 | First specific praised feature is the paywall design → **billing**. |
| `51573c5e` "Keeps playing the same song … freezing and crashing … [uninstalling]" | playback / cancellation / 5 | **Boundary case (label departs from the rubric):** intent **cancellation** is right (explicit departure), topic **playback** is right, but severity 5 requires explicit financial, privacy or data harm; crashes and cancellation intent alone do not raise severity, so the rubric gives 3–4. The author kept the original dev label; this is why dev severity agreement understates agreement with the written rule (README §4). |

The model sees compressed versions of these definitions ([`prompts/jev_tiny_v1.yaml`](../prompts/jev_tiny_v1.yaml)); the verifier sees the
full definitions ([`prompts/verify_v1.md`](../prompts/verify_v1.md)).
