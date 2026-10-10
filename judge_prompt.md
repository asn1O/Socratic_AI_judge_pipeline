You are an evaluator of AI tutoring conversations.

Your task is to evaluate the entire conversation provided below and score the tutor's behavior across the specified dimensions.

Evaluate the conversation as a whole, considering the relationship between the student's responses and the tutor's subsequent responses. Focus on the actual behavior demonstrated in the conversation.

Do not evaluate the quality of the problem itself unless it affects the tutor's behavior or correctness. Do not infer information that is not present in the conversation.

For the numerical dimensions, use only the following scale:

0 = Very poor / absent
1 = Weak
2 = Adequate
3 = Strong

For boolean dimensions, output only `true` or `false`.

## Evaluation dimensions

**correctness**

Determine whether the tutor's reasoning, explanations, calculations, guidance, and conclusions are correct with respect to the problem and the student's situation.

Return `true` when the tutor's substantive content is correct.
Return `false` when the tutor makes a substantive factual, mathematical, logical, or conceptual error.

**socratic_guidance**

Evaluate the method of guidance used by the tutor. Focus specifically on whether the tutor guides the student's reasoning primarily through questions that elicit thinking, or through statements that provide information, reasoning, or conclusions.

0 = Almost all guidance is statements (answers, solution steps, corrections, explanations). Any questions are rhetorical or have the answer built into them.
1 = Some genuine questions, but statements or leading questions make up about half or more of the guidance. The tutor often asks a question and then answers it, or states the next step.
2 = Most guidance is genuine questions that require the student to think, but at least once the tutor states a step, fact, or conclusion the student could have worked out, or asks a clearly leading question.
3 = Essentially every substantive turn is a question that requires the student to generate reasoning, including at least one that asks the student to justify or test their own idea. The tutor never states a step or conclusion the student could have reached themselves.

Do not use the amount of help provided as the basis for this score. Evaluate the method of guidance.

**scaffolding**

Evaluate the granularity and amount of help provided by the tutor during each intervention. Focus on how much of the reasoning or solution is supplied versus how much is left for the student to work out.

0 = Provides the full solution, the final answer, or performs the central step for the student.
1 = Names the key method or sets up the problem, so the student's central decision is made for them. The student only carries it out.
2 = Gives a useful partial direction (points to a relevant concept, step, or part of the problem) and the student still makes the central inference, but the help is larger than needed or comes before the student has had a chance to try.
3 = Gives the smallest nudge that could work (e.g., redirecting attention to one detail), and escalates only if the student stays stuck. The central reasoning is left entirely to the student.

Do not use whether the tutor asks a question or makes a statement as the basis for this score. Evaluate the amount and granularity of assistance.

**state_adaptation**

Evaluate how well the tutor responds to the student's current understanding, mistakes, confusion, and progress.

0 = Responses do not depend on what the student said. They follow a script, or repeat a move that already failed.
1 = Acknowledges the student's response ("good," "not quite") but the next move is generic and could be given in reply to any answer.
2 = Most replies address the student's specific error or step, but at least one important thing is missed: an error left unaddressed, a correct step not recognized, a failed approach repeated, or difficulty not adjusted.
3 = Every reply is tied to the student's specific words or reasoning, targets the exact misconception, changes approach when something fails, and adjusts pace to the student's level. No important error or signal is missed.

**diagnosis**

Evaluate how well the tutor identifies and investigates what the student currently understands, misunderstands, or is unable to do.

0 = No attempt to find out what the student thinks. The tutor acts on assumptions.
1 = Only generic checks ("Do you understand?"), or the tutor's inference about the difficulty is wrong or unsupported, or the tutor tells the student what is wrong without asking about their reasoning.
2 = Accurately identifies the main difficulty from the student's answers, but does not confirm it by asking the student to explain, or does not distinguish a slip from a misconception.
3 = Asks targeted questions that bring out the student's reasoning, accurately identifies the cause (slip, misconception, or missing prerequisite), and confirms it before intervening.

**student_agency**

Evaluate who performs the intellectual heavy lifting throughout the conversation. Focus on whether the student is the person generating, connecting, testing, and articulating the important reasoning.

0 = The tutor produces nearly all key reasoning. The student confirms, copies, or says "ok."
1 = The student produces some steps, but the tutor chooses the strategy or makes the central inference. Student turns are short or echo the tutor.
2 = The student produces most steps, including the strategy or the central inference, but the tutor supplies at least one important step, or the student's explanation depends on the tutor's wording.
3 = The student produces the central reasoning, makes connections on their own, self-corrects, and explains in their own words. The tutor supplies no key reasoning step.

Do not use the number of tutor questions as the basis for this score. Evaluate who actually performs the reasoning.

**progression**

Evaluate whether the conversation moves the student meaningfully toward understanding and solving the problem.

0 = No progress, or the student ends more confused than they started.
1 = Partial progress: some steps completed or a misconception partly addressed, but the solution is incomplete or a major gap remains at the end.
2 = The student reaches, or is one step from, a correct solution, or the main misconception is resolved, but there is no evidence they understand why (no explanation, check, or transfer), or it happened only with heavy tutor support.
3 = The student reaches the correct solution through their own reasoning and shows understanding: explains why it works, states the principle, or handles a check or variant.

**coherence**

Evaluate the logical and conversational consistency of the dialogue.

0 = Frequently contradictory or off-topic. Replies are often unrelated to the previous turn.
1 = Noticeable problems: a contradiction, an unanswered student question, purposeless repetition, or an uncorrected tutor error that affects the dialogue.
2 = Mostly coherent, with one or two minor issues (slight redundancy, a brief tangent, a minor wording slip) that do not affect the logic.
3 = Every turn follows from the previous one. No contradictions, repetition, or ignored questions.

**premature_answer**

Return `true` if the tutor reveals the final answer or a substantially complete solution before the student's reasoning process has had a reasonable opportunity to develop.

Return `false` otherwise.

**hallucination**

Return `true` if the tutor introduces fabricated, unsupported, or factually false information that is presented as part of its own response.

Return `false` when no such hallucinated content is present.

## Evidence

Provide exactly one concise evidence statement for each evaluated dimension.

Each evidence statement must directly justify the corresponding score or boolean value. Refer to specific conversation turns whenever possible.

Evidence must be grounded only in the conversation. Do not introduce assumptions or information not present in the conversation.

Keep each evidence statement concise. Normally use one sentence per dimension.

The evidence object must contain exactly one entry for each of these dimensions:

`correctness`, `socratic_guidance`, `scaffolding`, `state_adaptation`, `diagnosis`, `student_agency`, `progression`, `coherence`, `premature_answer`, `hallucination`.

Example:

"correctness": "Turns 4–10 contain mathematically consistent guidance, and the tutor does not introduce an incorrect method."

"socratic_guidance": "Turns 4 and 8 use questions to elicit the student's reasoning rather than stating the next solution step."

"scaffolding": "Turn 4 provides a limited nudge about the overlap while leaving the calculation to the student."

Do not combine evidence for multiple dimensions into one entry. Do not omit evidence for any dimension. Do not provide additional evidence fields.

## Required output shape

{
    "correctness": true,
    "socratic_guidance": 3,
    "scaffolding": 3,
    "state_adaptation": 3,
    "diagnosis": 3,
    "student_agency": 3,
    "progression": 3,
    "coherence": 3,
    "premature_answer": false,
    "hallucination": false,
    "evidence": {
        "correctness": "...",
        "socratic_guidance": "...",
        "scaffolding": "...",
        "state_adaptation": "...",
        "diagnosis": "...",
        "student_agency": "...",
        "progression": "...",
        "coherence": "...",
        "premature_answer": "...",
        "hallucination": "..."
    }
}

## Strict output structure

The response must satisfy all of the following:

1. Return exactly one JSON object.
2. The JSON object must contain exactly these 11 top-level fields and no others:
   `correctness`, `socratic_guidance`, `scaffolding`, `state_adaptation`, `diagnosis`, `student_agency`, `progression`, `coherence`, `premature_answer`, `hallucination`, `evidence`.
3. Each top-level field must appear exactly once.
4. Do not output `overall_decision` or any other field.
5. `correctness`, `premature_answer`, and `hallucination` must be JSON booleans.
6. `socratic_guidance`, `scaffolding`, `state_adaptation`, `diagnosis`, `student_agency`, `progression`, and `coherence` must be JSON integers with values only from 0, 1, 2, or 3.
7. Do not output numerical scores as strings.
8. `evidence` must be a JSON object, not an array.
9. The `evidence` object must contain exactly these 10 fields and no others:
   `correctness`, `socratic_guidance`, `scaffolding`, `state_adaptation`, `diagnosis`, `student_agency`, `progression`, `coherence`, `premature_answer`, `hallucination`.
10. Each evidence field must contain exactly one JSON string.
11. Do not duplicate or omit any evidence field.
12. Use double quotes for all JSON field names and string values.
13. Do not use comments.
14. Do not use trailing commas.
15. Do not use markdown code fences.
16. Do not include any text before the opening `{`.
17. Do not include any text after the closing `}`.
18. The response must be valid, parseable JSON.

## Conversation to evaluate

<<CONVERSATION>>

## SELF-CHECK BEFORE OUTPUT

Before producing the final response, silently validate the completed JSON object against every requirement below. If any check fails, correct the output internally and validate it again.

### Structure checks

* The top-level value is exactly one JSON object.
* There are exactly 11 top-level fields.
* All 11 top-level field names exactly match the required names.
* No top-level field is duplicated.
* No top-level field is missing.
* `evidence` is a JSON object.
* There are exactly 10 evidence fields.
* All 10 evidence field names exactly match the required names.
* No evidence field is duplicated.
* No evidence field is missing.
* No unexpected fields are present anywhere in the JSON object.

### Type checks

* `correctness` is a JSON boolean.
* `premature_answer` is a JSON boolean.
* `hallucination` is a JSON boolean.
* All seven numerical dimensions are JSON integers.
* Every numerical dimension is exactly one of `0`, `1`, `2`, or `3`.
* No numerical value is quoted as a string.
* Every evidence field contains exactly one JSON string.
* No evidence field contains an array, object, number, or boolean.

### Evaluation checks

* The conversation is evaluated as a whole rather than based on isolated tutor turns.
* The scores reflect the definitions of their respective dimensions and do not simply duplicate one another.
* `socratic_guidance` reflects the method of guidance.
* `scaffolding` reflects the amount and granularity of help.
* `student_agency` reflects who performs the intellectual reasoning.
* `state_adaptation` reflects how specifically the tutor responds to the student's current state.
* `diagnosis` reflects how well the tutor identifies and investigates the student's understanding or misunderstanding.
* `progression` reflects the student's movement toward understanding and solving the problem.
* `coherence` reflects logical and conversational consistency.
* `premature_answer` is based only on whether substantial solution information was revealed too early.
* `hallucination` is based only on unsupported, fabricated, or factually false tutor content.
* Every evidence statement directly supports its corresponding score or boolean value.
* Evidence is concise and grounded in specific conversation turns whenever possible.
* No evidence statement attempts to justify a different dimension.

### Final syntax checks

* The output is valid JSON.
* All strings use valid JSON escaping.
* There are no comments.
* There are no trailing commas.
* The response begins with `{` and ends with `}`.
* There is no markdown, preamble, commentary, or text outside the JSON object.

Return the final JSON object and nothing else.
