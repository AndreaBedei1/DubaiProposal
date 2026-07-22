# Project description (ready to paste — ~300 words)

Desalination keeps hundreds of millions of people supplied with fresh water,
and returns a concentrated by-product to the sea: brine. Because brine is
denser than seawater, it sinks and creeps along the seabed as a thin,
invisible layer that can stress the benthic ecosystems coastal communities
depend on. It is also exactly where routine monitoring is weakest: vessel
casts sample a handful of points a few times a year, and fixed stations
rarely sit in the bottom layer where the plume actually lives.

BrineWatch is an initial prototype of a repeatable, uncertainty-aware
screening tool built around hardware many labs already own: a BlueROV2-class
mini-ROV retrofitted with a low-cost conductivity–temperature payload. In
each mission the vehicle localizes the outfall structure from imaging-sonar
contacts accumulated across multiple viewpoints (starting only from an
approximate chart position — never from privileged knowledge), runs baseline
transects, and then lets a boundary-aware adaptive planner concentrate the
remaining battery where it matters most: the regulatory mixing-zone
boundary. A Gaussian-process model turns the sparse samples into a near-bed
salinity map with explicit uncertainty, and the mission ends with a
three-state screening result — CLEAR, REVIEW, or POSSIBLE EXCEEDANCE — that
refuses to declare an unsurveyed area compliant. Every mission produces a
self-contained digital record, so repeated surveys build a longitudinal
picture of a discharge site.

The current prototype runs end-to-end in the official HoloOcean marine
simulator against a controlled analytic plume surrogate, with the water
properties virtual and everything else — planning, mapping, screening,
reporting — implemented and benchmarked (20-seed equal-budget studies; zero
wrong conclusive screening results). The architecture isolates the simulator
behind one interface, so the physical transfer is a backend swap: the team's
own BlueROV2 and Omniscan 450 FS forward-looking imaging sonar are the target hardware, with a written
one-day water-test protocol as the next step. Robotic plume mapping is not
new; BrineWatch's aim is making it repeatable, honest about uncertainty, and
affordable for utilities, municipalities, regulators and university labs.
