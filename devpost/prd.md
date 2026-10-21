---
doc: prd
status: approved
---

# Speak Fluent — Product Requirements

A fully local English-speaking practice app for the learner on CachyOS Linux, with natural spoken conversation and useful feedback afterward.

Source: `scope.md > The Unique Kernel`, `Who It's For`, and `The POC Boundary`.

## The Core Journey

1. Open the app. The main area shows a microphone Start button and a simple robot character; old conversations are accessible on the left.
2. Press Start. The AI speaks first to begin an everyday conversation. Its words also appear as text.
3. Speak naturally, without pressing a button for each turn. The AI responds and asks relevant follow-up questions. If the user speaks while it is talking, it stops and listens.
4. Hide the AI's text when desired to focus on speaking and listening; show it again when needed.
5. Say goodbye or a similar farewell to end the practice conversation. The AI then delivers a spoken feedback report based on that conversation.
6. After the report, the main area shows the microphone button for starting another conversation. The completed conversation's transcript and report are available under old conversations.

Source: `scope.md > The Core Loop` and `What "Working" Looks Like`.

## Screens and Layout

- One app view with an old-conversations area on the left and a main area taking approximately the right 90% of the screen.
- The main area supports starting and conducting a conversation, receiving feedback, and viewing a selected old conversation.
- Opening an old conversation shows its speech transcript and feedback report.
- A visible control hides or shows the AI's speech text during practice.

Source: `scope.md > The Core Loop`; layout and history were added in the PRD interview.

## Look and Feel

- Simple 2D robot character.
- A balloon-like background that changes color while the AI speaks, including when it speaks the report.
- Exact colors and typography are unspecified; no additional design interview is required.

Source: `scope.md > Inspiration & Identity`, developed through the learner's visual direction.

## Features and Behavior

### Start and Spoken Conversation

The microphone Start button begins the session, with the AI speaking first. Conversation is hands-free after starting: the app recognizes when the user has finished a turn without requiring another button press. Replies relate to the conversation and include follow-up questions that keep everyday practice going. Corrections wait until the report.

The user can speak at any time during the conversation. When they interrupt the AI, its current speech stops and the app listens to their turn. Situation-dependent decisions about whether to continue speaking are deferred.

Breathing, coughing, and other non-speech sounds should not count as interruptions. A brief speech-confirmation window is acceptable to reduce false interruptions; verify the balance against real speech during the hands-on check.

**Acceptance criteria**
- Pressing Start produces an audible AI opening without requiring the user to speak first.
- A few spoken exchanges work without per-turn button presses.
- At least one AI follow-up is relevant to what the user said.
- Speaking during an AI reply stops its speech and allows the user's turn to be used for the next response.

Source: `scope.md > The Core Loop`, `The Unique Kernel`, and `The POC Boundary`.

### Speech Text and Speaking Animation

AI speech is visible as text by default. The user can hide and reveal it without ending the conversation or muting speech. Hiding text does not remove it from the completed transcript. The robot's balloon-like background changes color while the AI speaks.

Emojis may appear only with genuinely emotional AI replies (such as celebration or sympathy), not as routine decoration on greetings, ordinary questions, or every turn. They are silent decorations: voice output must skip them rather than pronounce emoji names. This preference was clarified during the first build's hands-on review.

**Acceptance criteria**
- The displayed text corresponds to the audible AI reply.
- Hiding text leaves spoken interaction working; showing it restores the text display.
- The background visibly changes during AI speech and returns to its non-speaking appearance when speech stops.

Source: `scope.md > Inspiration & Identity` and `The Core Loop`, expanded in the interview.

### Farewell and Feedback Report

A goodbye or similar farewell ends practice and triggers a spoken report. The report covers grammar mistakes, appropriate word choices, understandable wording, and ways to simplify unnecessarily complex sentences. It uses examples from the actual conversation and gives actionable alternatives where needed. It must not invent mistakes when no relevant issue was found. Understandability refers to wording, not pronunciation or accent grading.

An explicit closing request such as “end the conversation” also triggers feedback. Briefly spoken farewells must still be recognized when filtering out non-speech interruptions.

The report is also available as text in the saved conversation. As AI speech, its live text follows the show/hide control. After the report finishes, the microphone Start button is available again.

**Acceptance criteria**
- Saying a clear farewell transitions to feedback rather than another practice question.
- A conversation containing a clear wording or grammar mistake produces a report identifying it and suggesting an improvement.
- Suggestions for clearer or simpler wording refer to something the user actually said.
- The report is audible, can be read afterward, and is followed by the option to start a new conversation.

Source: `scope.md > The Core Loop`, `What "Working" Looks Like`, and `Explicitly Cut`.

### Old Conversations

The old-conversations area lets the user open a completed conversation and read its transcript and report. The transcript distinguishes the user's speech from the AI's speech; the report is presented separately from the practice exchange. Completed transcripts and reports are saved locally in a dedicated, human-readable file format, such as Markdown or plain text, and remain available after closing and reopening the app. The exact format and file organization will be decided in `4-spec`.

**Acceptance criteria**
- A completed practice session appears in old conversations.
- Opening it displays that session's user and AI turns and its feedback report.
- Starting another conversation produces a separate session rather than replacing the previous one.
- After closing and reopening the app, previously completed conversations can still be opened with their transcripts and reports intact.
- Saved conversation content can be read in a local Markdown or plain-text file without the app.

Source: extension of `scope.md > The Core Loop` requested during the PRD interview. History is limited to viewing transcripts and reports.

## States and Boundaries

- **First use / no history:** the microphone Start button is available; there are no old conversation entries yet.
- **Conversation:** the app supports listening, spoken replies, interruptions, and optional AI text.
- **Feedback:** practice has ended and the AI speaks its report.
- **Complete:** the transcript and report are available in history, and Start is available for another session.
- **Reopened app:** completed transcripts and reports remain available from their locally saved files.
- **Microphone or AI failure:** show a warning message describing the relevant problem. A failure must not appear as a successful response or completed report. Exact wording and recovery guidance can be refined in the technical plan.
- **Local operation:** after initial software and model downloads, speech recognition, conversation, speech output, and feedback must work offline without paid services.

Source: `scope.md > The POC Boundary`, plus the learner's warning requirement.

## Product Decisions

- AI speaks first after Start, lowering the effort required to begin practice.
- Hands-free conversation with immediate stopping on interruption is the initial version of natural turn-taking; situational interruption handling waits.
- A spoken farewell ends practice and leads to a spoken report.
- Clear speaking means understandable words and sentences, not pronunciation evaluation.
- AI text can be hidden to focus on speaking and listening.
- The robot and color-changing background provide the app's visual identity.
- The main area uses roughly 90% of the width; old conversations provide access to transcripts and reports.
- Completed conversations persist locally in dedicated human-readable files; Markdown or plain text is acceptable, with the exact format left to technical planning.

## What We're Building

One Linux proof of concept with AI-first offline spoken conversation, hands-free turns and interruption handling, optional AI text, a simple animated robot background, farewell-triggered spoken wording feedback, and access to completed transcripts and reports.

**Demonstration:** with internet disconnected after setup, start a session, complete a few relevant exchanges, interrupt an AI reply, hide and reveal text, say goodbye, hear an actionable correction, open the saved transcript/report, and start another session.

Source: `scope.md > What "Working" Looks Like` and `The POC Boundary`, expanded by the PRD interview.

## Deferred From the POC

- Situation-dependent interruption handling: stopping whenever the user speaks is the chosen first behavior.
- Accent grading and pronunciation assessment: feedback evaluates wording only.
- Job interviews, business meetings, debates, and travel scenarios: everyday conversation is the initial focus.
- Android support and broader distribution: prove the loop on the learner's Linux machine first.
- History features beyond reading transcripts and reports, such as audio replay, searching, and editing: these are not needed for the requested history view.

Source: `scope.md > Later` and interview decisions.

## Non-Goals

- Paid or cloud-dependent AI services.
- Continuous corrective interruptions during practice.

Source: `scope.md > Explicitly Cut`.

## Open Questions

- No unresolved product decisions block approval.
- **For `4-spec`:** verify that fully offline speech, hands-free turn detection, and interruption handling are feasible on the learner's RTX 5070 / 32 GB machine within the hackathon's 2–4 hours of active work. History is an addition to the approved scope; if the combined work exceeds that budget, return to the learner for a cut rather than silently weakening the conversation requirements.
- **For `4-spec`:** define actionable warning wording and recovery guidance for microphone and AI failures. No numerical response-time target has been agreed; the technical plan must investigate whether the experience supports natural conversation.
