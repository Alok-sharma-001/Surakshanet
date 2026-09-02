this section is basically explaining **how Surakshanet converts camera-detected traffic into a traffic-engineering decision for the traffic signal**.

The complete flow is:

**Camera detects vehicles → Convert them into PCU → Calculate junction demand → Decide green time → Apply safety constraints → Fallback if AI/sensor fails.**

---

## A. Why raw vehicle counting is not enough?

Suppose two roads have:

### Road A

- 20 motorcycles
    

### Road B

- 20 buses
    

A normal computer-vision system says:

> Both roads have **20 vehicles**, so traffic is equal. ❌

But physically this is obviously wrong. Twenty buses occupy far more road space and interfere with traffic much more than twenty motorcycles.

That is why we use **PCU — Passenger Car Unit**.

IRC:106-1990 explicitly explains PCU as a common unit used to express mixed-traffic capacity, with different vehicle types converted based on their relative interference with traffic.

---

# 1. What is PCU?

We take a normal passenger car as a reference:

> **1 Car = 1 PCU**

Then other vehicles are expressed relative to a car.

For example, conceptually:

|Vehicle|PCU idea|
|---|--:|
|Motorcycle|Lower than a car|
|Car|1|
|Auto-rickshaw|Around car-sized interference or somewhat more|
|LCV|More than a car|
|Bus/Truck|Much more than a car|

So if:

- 10 motorcycles × 0.5 PCU = **5 PCU**
    
- 10 cars × 1 PCU = **10 PCU**
    
- 2 buses × 3 PCU = **6 PCU**
    

Then total effective traffic demand:


**In simple words:** **Total PCU demand**=5+10+6=21\ PCU


Even though the camera detected:


**In simple words:** 10+10+2=22\ vehicles


the system understands the **effective traffic load as 21 PCU**.

---

# 2. Your formula

You wrote:


**In simple words:** D_{PCU}=the sum of all vehicle categories**number of detected vehicles in category k** multiplied by PCU_k


Let's break it down.

### (K)

Set of vehicle categories:


**In simple words:** **Vehicle categories = Motorcycle, Auto-rickshaw, Car, LCV, and Bus/Truck.**


### (**number of detected vehicles in category k**)

Number of detected vehicles of category (k).

Example:


**In simple words:** **Number of cars detected = 15.**


means 15 cars were detected.

### (PCU_k)

PCU conversion factor for that vehicle.

### Final result

Multiply the number of each vehicle by its PCU value and add everything.

Example:

# 
**In simple words:** **Total PCU demand** 20(0.5) + 10(1) + 5(1) + 2(1.5) + 1(3)



**In simple words:** =10+10+5+3+3



**In simple words:** {**Total PCU demand**=31\ PCU}


So Surakshanet will say:

> "This junction approach currently has an effective demand of **31 PCU**."

---

# Important correction about your PCU table

The values in your pasted text appear to have formatting errors, for example:

- `.5`
    
- `.0`
    
- `.5`
    
- `.0`
    

Also, the uploaded IRC:106-1990 table does **not simply give one universal fixed PCU value for every vehicle type**. On page 10, it shows recommended PCU factors that vary with the percentage composition of vehicle classes; for example, two-wheelers are shown as 0.5 or 0.75, passenger cars as 1.0, auto-rickshaws as 1.2 or 2.0, and trucks/buses as 3.7 or 5.0 depending on the composition column.

So for your hackathon documentation, I would **not claim that the fixed values are exactly the IRC table** unless you define them as your project's selected operational approximation.

A better wording would be:

> **“Surakshanet uses IRC:106-1990 PCU principles and project-selected PCU conversion factors calibrated for the deployed intersection.”**

That is technically safer.

---

# B. Signal Phase Constraints

Now suppose your AI calculates:

### Road A


**In simple words:** 80\ PCU


### Road B


**In simple words:** 20\ PCU


The naive AI might decide:

> Give Road A 60 seconds of green and Road B 2 seconds.

That would be a bad traffic signal system.

Therefore, you impose **constraints**.

---

## 1. Minimum Green Time

You wrote:


**In simple words:** **minimum green time**=10s


Meaning:

> Once a signal becomes green, it should remain green for at least 10 seconds.

### Why?

Imagine the AI is updating traffic every second:

- 12:00:00 → Road A busy → Green A
    
- 12:00:03 → Road B becomes busy → Green B
    
- 12:00:06 → Road A busy again → Green A
    

This is called unstable switching or **signal hunting**.

Drivers would get confused, and the intersection could become dangerous.

Therefore:


**In simple words:** **Green time must be at least 10 seconds.**


This gives stability.

---

## 2. Amber / Clearance Interval

After green, you don't immediately change to red.

You have:

### 🟢 Green → 🟡 Amber → 🔴 Red

For example:


**In simple words:** **amber time**=3s


During amber:

- Vehicles already close to the stop line can safely clear.
    
- Drivers get a warning that the phase is ending.
    
- The next traffic movement does not start immediately.
    

---

## 3. All-Red Interval

This is an extra safety period:

### Phase A

🟢 Green → 🟡 Amber → 🔴 Red

Then:

### ALL directions

🔴🔴🔴🔴

For around:


**In simple words:** T_{all-red}=1–2s


Then the next direction gets green.

### Example

```
North-South:  GREEN
East-West:    RED
        ↓
North-South:  AMBER
East-West:    RED
        ↓
North-South:  RED
East-West:    RED       ← ALL-RED
        ↓
North-South:  RED
East-West:    GREEN
```

This prevents a vehicle from one direction colliding with vehicles that have just received green from the other direction.

---

# C. How Surakshanet would actually use this

Imagine a four-way intersection.

The AI detects:

### North

- 20 motorcycles
    
- 10 cars
    
- 2 buses
    

Effective demand, using your selected factors:


**In simple words:** 20 motorcycles × 0.5 + 10 cars × 1 + 2 buses × 3



**In simple words:** =10+10+6=26\ PCU


### East


**In simple words:** 50\ motorcycles + 5\ cars



**In simple words:** 50 motorcycles × 0.5 + 5 cars × 1=30\ PCU


### South


**In simple words:** 10\ cars=10\ PCU


### West


**In simple words:** 5\ buses=15\ PCU


The system sees:

|Direction|Effective Demand|
|---|--:|
|North|26 PCU|
|East|30 PCU|
|South|10 PCU|
|West|15 PCU|

Therefore, the priority might be:


**In simple words:** East > North > West > South


The AI then calculates green durations proportionally, but constrained by:


**In simple words:** green time for movement imust be at least10s


and phase transitions include:


**In simple words:** Amber=3s



**In simple words:** All\ Red=1–2s


---

# D. What is the Webster's Method part?

This is important.

Your system has two modes:

## 🤖 Mode 1: Adaptive AI Mode

```
Camera
   ↓
YOLO / CV detects vehicles
   ↓
Vehicle classification
   ↓
PCU conversion
   ↓
Calculate demand
   ↓
AI determines phase priority
   ↓
Dynamic green time
```

This is the normal intelligent mode.

---

## ⏰ Mode 2: Failsafe Webster / Time-of-Day Mode

What happens if:

- Camera disconnects?
    
- Edge device crashes?
    
- Network fails?
    
- Detection confidence becomes extremely low?
    
- AI produces invalid output?
    

You **must not let the intersection stop working**.

So:

```
AI/CV Failure
      ↓
Fallback Controller Activated
      ↓
Time-of-Day Traffic Profile
      ↓
Preconfigured Signal Cycle
```

For example:

### Morning peak: 8–10 AM

```text
North-South Green: 50 sec
East-West Green:   40 sec
```

### Afternoon

```text
North-South Green: 35 sec
East-West Green:   35 sec
```

### Evening peak

```text
North-South Green: 60 sec
East-West Green:   45 sec
```

This means even if the entire AI system dies:

> **The traffic signal still operates safely.**

This is a very strong feature for a hackathon because it shows that Surakshanet is not just an AI demo—it considers **real-world safety and reliability**.

---

# The entire concept in one diagram

```text
                    CCTV / Edge Camera
                           │
                           ▼
                  Vehicle Detection
                    (YOLO / CV)
                           │
                           ▼
               Motorcycle / Car / Bus
                    / Auto / LCV
                           │
                           ▼
                    PCU Conversion
                           │
                           ▼
               Effective Demand (PCU)
                           │
                           ▼
                Signal Optimization Engine
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        AI AVAILABLE?                 FAILURE
              │                         │
             YES                        ▼
              │                Webster / ToD Plan
              ▼                         │
      Dynamic Green Time                │
              │                         │
              └───────────┬─────────────┘
                          ▼
                 SAFETY CONSTRAINTS
                 • Min Green ≥ 10s
                 • Amber = 3–5s
                 • All Red = 1–2s
                          │
                          ▼
                   TRAFFIC SIGNAL
```

### In one sentence:

**PCU tells Surakshanet how much traffic is actually occupying the road, the optimization engine decides which movement deserves priority, safety constraints prevent dangerous rapid switching, and the Webster/ToD fallback keeps the intersection operational if AI or sensors fail.**

Also, for your documentation, I would verify **IRC:93-1985 and the exact minimum-green/amber/all-red values separately** before presenting those specific numbers as direct IRC requirements; the uploaded IRC:106-1990 source supports the PCU concept and its table, but not those signal-timing claims.

