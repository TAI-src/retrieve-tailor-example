---
title: Optimisation for a Fleet of Healthcare Vehicles
authors:
    - Sarah Thomson
date: 2026-01-16
link: https://dl.acm.org/doi/abs/10.1145/3638530.3664137
id: 1
---

# [Optimisation for a Fleet of Healthcare Vehicles](https://dl.acm.org/doi/abs/10.1145/3638530.3664137)

## Problem Description
(Describe the application context and the problem you are trying to solve)

A healthcare provider in a region of Scotland (Argyll and Bute) wanted to reduce their vehicle fleet size while still being able to cater for all trips. They provided 4 months of historical data about where their existing fleet were based and the trips they conducted, including start and end times and geographic location. We were also given information about the vehicle types and which vehicles were allowed to do which trips.

## Why was tailoring needed?
(Explain why existing methods were not sufficient and why tailoring was necessary.)

Not too much tailoring was needed but there were some particulars that had to be accounted for:

1. Jobs (i.e. trips) have a type of vehicle which (historically) executed them, but if needed certain other types of vehicles can do the trip.  For example, a small car originally did the trip, can be done by a van.
2. Vehicles can be swapped between geographical bases if needed and if the swap does not mean that the vehicle home base cannot cover its own trips.
3. It does not make sense to try and remove a type of vehicle from a base if there are none there or maybe if there are a small amount there. This led to a semi-guided mutation design.

## Baseline algorithm
(Name the algorithm you started from (if it exists) and explain the choice.)

Upper level: stochastic local search; lower level: constructive heuristic.

Motivations for choice: we wanted to keep it simple as possible and explainable for the user. No need to use fancy algorithms if a simple approach can obtain results.

## Tailoring process
(Describe the steps you took to tailor the algorithm including unsuccessful attempts.)

Adding in constraints (part of the operators); added additional vehicle/machine swap operation; semi-guided mutation.

## What was tailored
(Problem model, mutation operator, etc?)

Aspects of the algorithmic operators were tailored. This included the nature of the mutation operator and how it ensured that mutated solutions are feasible within the specific constraints of the problem.

## Main problem characteristics
(Describe the main characteristics of the problem. Provide comma-separated keywords.)

Choose most important ones: low-dimensional at upper level, high-dimensional at lower level; highly constrained (some soft and some hard); offline; there is an existing solution that works(current fleet); is a simplified version of what is eventually sought (optimising routes, carbon as well); low data sensitivity.

## References
(Provide any additional references, links, or citations related to your example.)

_No response_

## Author

Sarah Thomson