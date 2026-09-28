# Round Zero — video script (reviewed + corrected)

## What changed, and why

- **0:30–1:00** — "behavioral" replaced with "technical leadership" (the actual sixth round type with a real interviewer today; there's no "behavioral" round type in the app).
- **1:00–1:35** — "interview difficulty" replaced with "domain" (the real Setup field). The claim that expectations differ by level is corrected: level affects which *scenario* you get, but every session is graded against the same fixed Staff/Principal-caliber bar today, regardless of the level selected — that's a deliberate pilot-stage choice, not a bug, and it's worth saying so honestly rather than implying full level-differentiated grading exists.
- **0:30–1:00** — added a catchier breadth pitch: full loops vs. single rounds, and the real role/domain variety, per your ask. Everything named here is actually live today except the Hiring Manager round, called out explicitly as "coming soon" — a fair thing to tease since you said it's fine if a feature isn't there yet.
- **1:35–2:45** — added a stage direction to use Text format for the live demo, for recording reliability.
- **2:45–3:50** — the dimension list now matches the real ten rubric dimensions instead of a paraphrased seven, since viewers will see the actual labels on screen while you talk.
- **End of report section** — "longer-term goal" for progress tracking upgraded to present tense, since the Progress page's trend charts are live now, with a suggested few seconds showing it.
- Total runtime is now closer to ~5:30–5:45 with the loop/domain/role addition on top of the earlier fixes — a fair bit over your original 3–4 min target. Two easy trims if you want it shorter: in the 0:30–1:00 section, name 3–4 round types instead of all six ("...like coding, ML system design, and a few others"), or drop to one role/domain example each; in the evaluation-dimensions section (2:45–3:50), name 5–6 dimensions and say "and a few others." Either trim alone gets you back close to 4:30–5:00.

---

**[0:00–0:30 — Face to camera]**

Hi everyone, I'm Pawan.

Over the past few months, I've been building something called Round Zero—an AI-powered platform for realistic technical interview practice.

I call it Round Zero because it is the interview you take before the real interview: a safe place to practise, make mistakes, receive detailed feedback, and improve before speaking with an actual hiring team.

This weekend, I'm inviting a very small group of people to test the first version. Before I explain the pilot, let me quickly show you how Round Zero works.

**[0:30–1:00 — Share the Round Zero home screen]**

Here's the thing I think makes Round Zero different: you're not stuck with one rigid format.

You can build a full interview loop—stringing together coding, ML depth, ML system design, backend system design, technical leadership, and cross-functional rounds, back to back, just like a real onsite. Or, if you only want to drill one thing today, you can jump straight into a single round on its own—say, just ML system design, or just coding—and come back for the rest later. A hiring manager round is coming soon too.

It also adapts to who you actually are: pick your role—ML engineer, applied scientist, backend engineer, research scientist, and a few others—and your domain, whether that's LLMs, computer vision, ML infrastructure, or something else. Round Zero tailors the scenario to fit.

For this initial pilot, I'm deliberately focusing the test on one experience: ML system design. But the rest of the loop is already there, and I'll be opening it up as the pilot progresses.

The objective is not simply to give you a list of questions. Round Zero should behave more like a real interviewer: understand your answer, identify areas that need clarification, and ask relevant follow-up questions.

**[1:00–1:35 — Show interview selection and configuration]**

Let's start an interview.

Here, the candidate can select the interview type and provide information such as the target role, experience level, and domain.

For this demonstration, I'll select ML system design at the senior or staff level.

Round Zero uses that context to pick an appropriate scenario. I'll be upfront about one thing, though: for this pilot, every session is evaluated against the same bar — Staff/Principal-level expectations — no matter which level you select. Level-specific grading is on the roadmap, but right now the goal is to measure everyone against the highest real bar, so the feedback means something even if it's tough.

**[1:35–2:45 — Show the active interview]**

*(Use Text format for this demo, not Voice — more reliable to record.)*

Once the session begins, the AI interviewer introduces the problem and gives the candidate an opportunity to ask clarifying questions.

[Allow the AI interviewer's opening question to play.]

Now I can begin explaining my approach just as I would in a real interview—starting with the business objective, users, functional requirements, scale, and key constraints.

[Show a short prerecorded answer or give a brief live response.]

The interviewer listens to the response and generates follow-up questions based on what was actually discussed.

[Allow an adaptive follow-up question to play.]

For example, if I describe the high-level architecture but don't explain capacity planning, failure recovery, model evaluation, or a key design trade-off, the interviewer can probe that area.

The intention is to make the conversation adaptive. It should not feel like a static questionnaire where every candidate receives the same sequence regardless of their answers.

[If available, briefly show the timer, transcript, notes, or whiteboard—but don't explain every control.]

The candidate can also structure the solution using the available workspace while continuing the conversation with the interviewer.

**[2:45–3:50 — Open the evaluation report]**

After the interview, Round Zero generates a detailed evaluation report.

This is one of the areas I care about most. A score alone is not very useful. Candidates need to understand why they received that score and what they should do differently next time.

The report evaluates ten dimensions, including:

*(if you want to trim toward 4 minutes, this is the easiest place — naming 5–6 of these and saying "and a few others" reads just as well on camera)*

* Problem framing and requirements
* High-level architecture
* ML and model reasoning
* Data and training
* Serving and scalability
* Reliability
* Evaluation and monitoring
* Cost and efficiency
* Trade-off reasoning
* Communication

[Scroll slowly through the report.]

The evaluation highlights strengths, identifies missed areas, and connects its conclusions to evidence from the interview.

It then provides specific improvement recommendations—not simply generic advice such as "add more detail."

And this part isn't just a future plan anymore — Round Zero now tracks your performance across multiple interviews, so you can actually see whether you're improving, which dimensions keep coming up as weak, and how close you are to being ready.

[Briefly show the Progress page — the readiness-over-time chart and per-dimension trend tiles.]

**[3:50–4:30 — Return to face to camera]**

Round Zero is still at an early stage, and that is why I'm looking for a small set of serious test users.

For this pilot, I plan to select only four or five people who are actively preparing for ML or AI interviews.

Selected participants will be asked to complete one or two ML System Design interviews, review their evaluation reports, and share candid feedback with me through a short conversation.

The pilot will be free. In return, I'm looking for thoughtful feedback about the realism of the interview, the quality of the follow-up questions, the accuracy of the evaluation, and what needs to improve.

**[4:30–4:55 — Application page or Google Form on screen]**

If you are interested, please complete the short application form linked with this post.

Because this is a small pilot, I may not be able to select everyone in the first group. However, the form will also help me identify participants for future testing rounds.

Thank you for following the work I'm doing through Architecting Intelligence—and for helping me shape Round Zero into something genuinely useful for ML and AI professionals.

I'm looking forward to hearing from you.
