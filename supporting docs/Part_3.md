Bhai, this section is the **actual intelligence core of Surakshanet**.

The previous sections answered:

- **What traffic data do we measure?** → PCU-based demand
    
- **Why is Surakshanet different?** → vision + prediction + signals + rerouting
    

This section answers:

> **“How exactly does the AI decide when to keep a signal green, switch it, and prepare for future congestion?”**

There are two major algorithms:

1. **MARL** → controls traffic signals **now**
    
2. **LSTM + XGBoost** → predicts traffic **in the future**
    

---

# A. Multi-Agent Reinforcement Learning for Signal Control

## What is MARL here?

Imagine a city with 10 intersections:

```text
**In simple words:** A] ─── [B] ─── [C
 |       |       |
**In simple words:** D] ─── [E] ─── [F
 |       |       |
**In simple words:** G] ─── [H] ─── [I
```

Instead of having one huge AI controlling the entire city:

```text
One Central AI
      ↓
Controls every signal
```

MARL treats intersections as **multiple agents**:

```text
Agent A → controls Intersection A
Agent B → controls Intersection B
Agent C → controls Intersection C
```

Each agent observes its local traffic and makes decisions.

Hence:

> **Multi-Agent Reinforcement Learning = multiple AI decision-makers learning to control multiple intersections.**

---

# 1. State Space

Your formula is:
**Queue length on each approach:** These are the queue lengths for each road approach, measured in PCUs. For a four-way intersection, this means the North, East, South, and West queues.

This simply means:

> **What information does the AI see before making a decision?**

---

## **Queue lengths on the different approaches, measured in PCUs.**

These represent queue lengths on different approaches, measured in **PCUs**.

Suppose a four-way intersection:

```text
                North
                  │
                  │
West ─────────────┼──────────── East
                  │
                  │
                South
```

The AI might see:

```text
North = 40 PCU
East  = 15 PCU
South = 8 PCU
West  = 35 PCU
```

So:

# [  
**In simple words:** q N,q E,q S,q W**In simple words:** 40,15,8,35

This is better than raw vehicle counts because the queue includes the effective occupancy of motorcycles, cars, buses, etc.

---

## (v_{avg}): Average velocity

Example:

```text
North:  4 km/h
East:  20 km/h
South: 30 km/h
West:   6 km/h
```

Low speed usually indicates:

- congestion,
    
- queue formation,
    
- slow discharge.
    

So even if two roads have similar PCU values, velocity can help distinguish their operational condition.

---

## (t_{elapsed}): Current phase duration

Suppose North-South has been green for:
**The current green phase has been active for 25 seconds.**
The AI needs this information because it cannot keep changing signals randomly.

For example:

```text
Current phase = North-South Green
Elapsed time = 25 sec
```

If minimum green is 10 seconds:
**25 seconds is greater than the 10-second minimum, so the controller is allowed to change the signal phase.**
Therefore switching is allowed.

---

## (_{current}): Current active phase

For example:

```text
Φcurrent = North-South Green
```

or:

```text
Φcurrent = East-West Green
```

This is essential because the AI must know what it is currently doing before deciding its next action.

---

# Example Complete State

At one moment:
**In simple words:** s t=[ 40,, 15,, 8,, 35,, 12 km/h,, 25 sec,, North-South Green

In normal language:

> North has heavy traffic, West is also congested, East and South are relatively light, average speed is low, and the current North-South green has lasted 25 seconds.

The AI receives this state and decides what to do next.

---

# 2. Action Space

You have defined:
**The AI has two possible actions: either extend the current green phase or switch to the next signal phase.**
This means the AI has only **two possible decisions**.

---

## Action 0 → Extend Green
**Action 0:** Keep the current green phase for another 5 seconds.
Meaning:

> Keep the current signal phase green for another 5 seconds.
**Each green-time extension adds 5 seconds.**
Example:

```text
Current:

North-South → GREEN
Elapsed      → 25 sec

AI chooses a = 0
        ↓

North-South remains GREEN
Elapsed becomes 30 sec
```

But only until:
**Maximum green time:** a green phase can remain active for up to 60 seconds.
So the AI cannot do:

```text
North-South Green for 5 minutes ❌
```

because:
**The green phase cannot exceed 60 seconds.**
---

## Action 1 → Change Phase
**Action 1:** Start changing to the next signal phase.
Meaning:

> Start the transition to the next phase.

For example:

```text
North-South GREEN
       ↓
North-South AMBER
       ↓
ALL RED
       ↓
East-West GREEN
```

But switching is only allowed if:
**A phase change is allowed only after the current green phase has reached its minimum duration.**
So if:
**Minimum green time:** 10 seconds.
and the current green has only lasted 6 seconds:

```text
AI wants to switch
      ↓
Not allowed ❌
```

This is a very important concept called **action masking or constrained action selection**.

The MARL agent may theoretically output:
**In simple words:** a=1
but the traffic controller checks:
**A phase change is allowed only after the current green phase has reached its minimum duration.**
If false:

> Reject the switch and continue safely.

---

# So the signal-control loop becomes

```text
Camera observes traffic
        ↓
Calculate PCU queues
        ↓
Create State sₜ
        ↓
MARL Agent
        ↓
 ┌──────────────┐
 │ Action aₜ    │
 ├──────────────┤
 │ 0 = Extend   │
 │ 1 = Switch   │
 └──────────────┘
        ↓
Safety Constraint Check
        ↓
Signal Controller
        ↓
New Traffic State
        ↓
Repeat
```

---

## 3. Reward Function

Your reward function tells the reinforcement-learning system what good traffic control looks like.

### First component: Queue and traffic delay

The AI should receive a better reward when:

- traffic queues are shorter,
- vehicles spend less time waiting,
- important traffic, such as emergency vehicles, receives the required priority.

The queue component considers the traffic demand on the different approaches and gives higher importance to vehicle categories that have a larger priority weight.

**Example:** If the total weighted queue is 95 PCUs, this contributes to the traffic-congestion part of the reward.

### Second component: Waiting-time penalty

The AI should be discouraged from allowing vehicles to wait for long periods.

**Example:** If the combined waiting time across all movements is 500 seconds, the system applies a larger delay penalty than it would for a much smaller waiting time.

### Third component: Switching penalty

The controller should avoid changing signal phases unnecessarily.

- **If the signal changes phase:** a switching penalty is applied.
- **If the signal stays in the current phase:** no switching penalty is applied.

**Example:** If the switching penalty is set to 10 points, an unnecessary signal change reduces the reward by 10 points.

### Overall meaning of the reward

In simple words, the AI is rewarded for **reducing queues and waiting time while avoiding unnecessary signal changes**.

This gives the reinforcement-learning agent a clear objective: **keep traffic moving efficiently without making unstable or unnecessary signal decisions.**


