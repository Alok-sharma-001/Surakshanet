# 22 — Hackathon Demo: Script, Checklists & Judge Q&A

Covers **SN-135 … SN-138**. The demo emphasises **measured outcomes, not feature count**.

---

## 1. Four-minute demo script

Open on the problem, not the product. Never say "and here is our dashboard."

| Time | Beat | On screen | What to say |
|---|---|---|---|
| 0:00 | **The problem** | Scenario A running, fixed-time, baseline delay counter | "This corridor runs the same signal plan at 5 PM that it runs at 3 AM." |
| 0:30 | **The proof** | Split screen: Webster vs DQN, same seed, delay counters diverging live | "Same traffic, same second, two controllers. The agent is paid to shrink the queue. Watch the gap." — then land the measured number *with its seed*. |
| 1:15 | **Ambulance** | Corridor propagating junction by junction on ETA; then the recovery chart | "Green ahead of it, normal behind it. And here's what happened to cross traffic — recovered in four minutes. We measured that, because a corridor that paralyses the rest of the city isn't a solution." |
| 2:00 | **Tomorrow's rally** | Event created; two SUMO worlds run; ranked routes; operator clicks Accept | "Everything so far reacted to traffic. This predicts it — before it exists." |
| 2:40 | **The citizen screen** | Cut to a phone showing the advisory that click just produced | "That one click reached commuters. Not a dashboard for the control room — information for the people stuck in the traffic." |
| 3:10 | **Incident + honesty** | Lane blocked; "Possible incident — 3 of 5 indicators", UNVERIFIED; operator confirms; reroute; warning | "It says *possible*, because a camera can flag an anomaly — it cannot certify a crash. A person confirms before this city hears anything." |
| 3:40 | **Close** | Network delay returning to baseline; state simulated vs real plainly | "Signals in simulation, detection on real video, control logic that speaks the protocol real cabinets use — with the cabinet keeping veto power." |

**Delivery rules:**
- Every number spoken is on screen and was measured. Never quote a figure the audience cannot see.
- Always say the seed when quoting the A/B result.
- Do not enumerate features. The story carries them.
- If a subsystem is down, show the honest unavailable state and continue — do not improvise a claim.

---

## 2. Pre-demo checklist (SN-135)

**T-60 minutes**
- [ ] `./reset.sh && ./start.sh` → all-green on `/health/deep`
- [ ] `make test-critical` green
- [ ] `make verify-determinism` green
- [ ] Seed confirmed as 42 in the startup banner
- [ ] All five scenarios load and switch in < 15 s
- [ ] A/B run completes and produces a figure
- [ ] Vision worker running on the demo clip
- [ ] Citizen view loads on the phone, on the venue network **and** on a hotspot
- [ ] Audit page shows rows from the rehearsal
- [ ] Backup video accessible **offline**, not from a cloud link

**T-5 minutes**
- [ ] `./reset.sh` for a clean state
- [ ] Browser tabs pre-opened: dashboard, A/B panel, events, public view, audit
- [ ] Phone unlocked, screen timeout disabled, on the public view
- [ ] Screen mirroring tested
- [ ] Laptop on mains power, notifications and sleep disabled

---

## 3. Backup video checklist (SN-136)

A recorded fallback has saved more hackathon teams than any feature.

- [ ] Full clean run, all seven beats, 4 minutes
- [ ] 1080p, readable at projector scale (test on an actual projector)
- [ ] Numbers legible when compressed
- [ ] No credentials, tokens or personal data visible on screen
- [ ] Stored **locally** on the presenting laptop and on a USB drive
- [ ] Playable offline in a player already installed
- [ ] The team knows the exact timestamp of each beat, so any single beat can be jumped to

---

## 4. Judge Q&A (SN-138)

### Technical

**"Show me the AI actually making a decision."**
Open `GET /signals/junctions/{id}/decision` or the control panel. It returns the 8-dim state vector, both Q-values, the chosen action, whether the safety envelope clamped it, and the reason — for the phase change just observed. Every decision is also a row in `control_decisions`.

**"Is the model actually trained, or is this a heuristic?"**
It is a DQN with a replay buffer and target network, trained in SUMO on this corridor; weights are on disk and the file hash is reported as `model_version` in every decision. Inference runs greedy with epsilon 0. Webster is the baseline it is measured against.

**"How do I know the improvement number is real?"**
Two SUMO instances, identical network, demand and **seed**, differing only in controller — and both under the same safety envelope, so the comparison measures the policy, not the constraints. The formula is `(baseline − ai) / baseline × 100` for cost metrics, computed server-side from simulation output and stored with its seed. Change the seed and the number changes.

**"Why only two actions?"**
Extend or advance. The agent never invents a phase — it only chooses *when* to switch between phases already defined in the network. That is what makes the safety envelope simple and the hardware story credible.

### Safety

**"What happens if the AI is wrong?"**
Three layers. First, the safety envelope: min green, max green, mandatory amber and all-red, and a pedestrian-service guarantee, all enforced *outside* the policy — the network has no path around them. Second, precedence: emergency pre-emption, operator override and the pedestrian guarantee all outrank the policy. Third, audit: every decision is logged with its inputs, so a wrong decision is reviewable. And any degradation falls back to Webster fixed-time, which is what the junction runs today.

**"Can this control real traffic lights?"**
Not today, and we do not claim it. We emit phase-change *intents*, not voltages. Real deployment adds an adapter speaking NTCIP 1202 or the vendor's cabinet API, and **the cabinet's conflict monitor keeps veto power** — it can physically refuse an unsafe request. The path is shadow mode → single-junction supervised pilot → corridor.

### Data & models

**"Where did your training data come from?"**
Three different answers, and we keep them separate. The DQN was trained in SUMO on this corridor — simulation data. The forecaster was trained on **synthetic** profiles, which we declare in every API response as `training_data: "synthetic"`; it has learned its own generator, not Indian traffic, and it needs a real city feed before it means anything. YOLOv8n uses pretrained COCO weights — which is also why it has no auto-rickshaw class, so autos are counted as cars or motorcycles and our PCU is biased. That is a documented limitation.

**"How do you detect drunk driving?"**
We don't, and no camera can — there is no visual signature of blood alcohol content. What the system can do is flag anomalous driving behaviour: weaving, erratic speed, unsafe headway. That flag routes to a patrol; an officer stops the vehicle; a calibrated breathalyser produces the actual measurement. AI narrows where to look. It never determines the offence.

**"Is your accident detection a trained crash classifier?"**
No, and we would not trust one built in a week — crashes are rare events and a model trained on a handful of clips false-positives on every hard brake. We use multi-indicator anomaly detection: speed collapse, stationary vehicle outside a queue, occupancy spike, downstream flow drop, queue anomaly. That is how real ATMS incident detection works. The output is "possible incident, 3 of 5 indicators" and it is unverified until an operator confirms.

### Privacy

**"You're processing CCTV — what about privacy?"**
Blur by default: faces and plates are blurred before anything is written to disk, so an unblurred frame never exists at rest. ANPR is off by default and gated behind a config flag that would need a stated legal basis. Retention is 72 hours for frames, one year for derived counts, per-case for incident evidence. Every access and every consequential action is audited. And dismissed flags are purged at 90 days — we don't retain disproven suspicion.

**"What stops an operator abusing the green corridor?"**
Corridor activation is restricted to emergency services and admins, rate-limited to five per minute, and every activation writes an audit row with the actor. The audit page is in the demo.

### Scalability & differentiation

**"Does this scale beyond four junctions?"**
The architecture does: stateless API workers, Redis pub/sub fanout so WebSockets work across workers, TimescaleDB hypertables for telemetry, and one independent agent per junction so control scales horizontally. What we have *not* proven is coordinated control at city scale — a per-junction agent does not optimise a network. Gating between adjacent junctions is our current spillback answer, and we would name network-level coordination as the next research problem rather than claim it.

**"How is this different from existing adaptive signal systems?"**
Two things. First, we can *prove* the benefit: same demand, same seed, baseline and AI side by side, measured. Most adaptive deployments cannot show you their counterfactual. Second, the public half — one operator decision becomes a citizen advisory before the jam exists. Existing systems optimise the network and tell nobody.

**"What's the weakest part of this project?"**
The forecaster is trained on synthetic data, so its predictions are architecture demonstrations rather than validated forecasts. And our DQN is validated in simulation only. We would rather tell you that than have you find it.

*(Answering this one straight is worth more than deflecting it. Judges ask it to see whether the team knows.)*
