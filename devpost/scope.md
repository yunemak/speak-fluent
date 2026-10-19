---
doc: scope
status: approved
---

# Speak Fluent

A free, fully local English-speaking practice app for natural conversations with AI.

## The Unique Kernel
Practice speaking with no fear: an offline conversation partner keeps everyday conversations going, then offers useful corrections without constantly interrupting the practice.

## Who It's For
The learner, who wants to improve their own spoken English through natural, interactive conversations. Their first device runs CachyOS Linux with an RTX 5070 and 32 GB RAM. Their current practice routine has not been discussed.

## The Core Loop
Open the app, speak into the microphone, hear the AI respond, and continue the conversation through relevant follow-up questions. End the conversation and receive corrections and personalized feedback on wording. Return for more speaking practice.

## Inspiration & Identity
The experience should make it comfortable to speak without fear and keep conversation alive and interesting. No visual references or aesthetic choices have been established.

## Why This Matters to the Learner
The main goal is a useful tool for improving their own English speaking skills. They also hope to share the app with everyone for free and learn how local apps and AI speech work.

## What "Working" Looks Like
On the learner's Linux machine, complete a few spoken exchanges with audible AI replies entirely offline, then receive useful feedback tied to the conversation. The demonstration should show both a relevant follow-up and an actionable wording correction when there is something to correct.

The hackathon targets 2–4 hours of active work and requires a short demo video and public GitHub repository; deployment is optional. Local model setup and performance must be checked during technical planning rather than assumed.

## The POC Boundary
- CachyOS Linux on the learner's machine is the first target.
- Spoken everyday conversation: microphone input, local AI responses, and spoken output.
- Follow-up questions that sustain the conversation.
- Corrections and personalized wording feedback after the conversation.
- No paid services or runtime cloud dependencies; speech recognition, conversation generation, and speech output all run locally.
- Initial software and model downloads may require internet access; practice must work offline after setup.

## Later
- Accent grading and pronunciation assessment: a separate capability requiring reliable evaluation beyond recognizing words.
- Job interviews, business meetings, debates, and travel scenarios: everyday conversation proves the initial loop.
- Android support: begin with one platform.
- Broader free distribution: a long-term goal beyond proving the app works on the learner's machine.

## Explicitly Cut
- Paid or cloud-dependent AI services: incompatible with the learner's fully local, free-of-charge requirement.
- Continuous corrective interruptions during conversation: the agreed prototype gives feedback afterward to preserve conversational flow.
