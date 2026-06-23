PASS

# M19 WS-idle calibration

Verdict: `PASS`
max_mid_answer_gap: `4.989 s`
Recommended N: `8 s`
Margin above ceil(max_mid_answer_gap): `3 s`
Worst-case added latency: `8 s` (observed worst on these turns: `5.398 s`)

Safety: attach-only CDP to 127.0.0.1:9222, own tab via context.new_page(), no /json/list, temporary-chat indicator verified before sending, four prompts maximum with >=5 s send spacing, websocket frame evidence is timing/direction/opcode/payload length only, no frame text/header values/cookies/conversation text/ids recorded, own tab closed; browser not quit.

## Per-prompt gap tables (timing/length only; no payloads)

### Prompt `pong`

- t0_send: 0.000 s rel
- t_domdone: 10.791 s rel (stop gone + assistant length non-empty + stable ~3s)
- t_firstframe: 1.493 s rel
- t_lastframe: 7.965 s rel
- t0_to_firstframe (not counted as a mid-answer inter-frame gap): 1.493 s
- lastframe_to_domdone: 2.827 s
- max inter-frame mid-answer gap: 4.777 s

| # | t_rel_s | direction | opcode | payload_len_bytes | gap_since_prev_frame_s |
|---:|---:|---|---:|---:|---:|
| 1 | 1.493 | sent | 1 | 122 | n/a |
| 2 | 1.624 | recv | 1 | 14683 | 0.131 |
| 3 | 2.435 | recv | 1 | 1758 | 0.811 |
| 4 | 2.576 | recv | 1 | 1104 | 0.141 |
| 5 | 2.643 | recv | 1 | 174 | 0.067 |
| 6 | 2.644 | recv | 1 | 180 | 0.000 |
| 7 | 7.421 | recv | 1 | 2045 | 4.777 |
| 8 | 7.498 | recv | 1 | 1331 | 0.077 |
| 9 | 7.545 | recv | 1 | 1799 | 0.047 |
| 10 | 7.855 | recv | 1 | 567 | 0.310 |
| 11 | 7.910 | recv | 1 | 309 | 0.055 |
| 12 | 7.910 | sent | 1 | 111 | 0.000 |
| 13 | 7.918 | recv | 1 | 350 | 0.008 |
| 14 | 7.965 | recv | 1 | 124 | 0.047 |

### Prompt `one-sentence-ocean`

- t0_send: 0.000 s rel
- t_domdone: 14.066 s rel (stop gone + assistant length non-empty + stable ~3s)
- t_firstframe: 1.506 s rel
- t_lastframe: 11.464 s rel
- t0_to_firstframe (not counted as a mid-answer inter-frame gap): 1.506 s
- lastframe_to_domdone: 2.602 s
- max inter-frame mid-answer gap: 4.220 s

| # | t_rel_s | direction | opcode | payload_len_bytes | gap_since_prev_frame_s |
|---:|---:|---|---:|---:|---:|
| 1 | 1.506 | sent | 1 | 122 | n/a |
| 2 | 1.604 | recv | 1 | 7605 | 0.098 |
| 3 | 2.539 | recv | 1 | 1759 | 0.935 |
| 4 | 2.696 | recv | 1 | 1104 | 0.157 |
| 5 | 3.361 | recv | 1 | 180 | 0.665 |
| 6 | 7.581 | recv | 1 | 350 | 4.220 |
| 7 | 7.698 | recv | 1 | 2011 | 0.117 |
| 8 | 10.875 | recv | 1 | 2045 | 3.177 |
| 9 | 10.937 | recv | 1 | 1331 | 0.062 |
| 10 | 10.968 | recv | 1 | 1895 | 0.031 |
| 11 | 11.322 | recv | 1 | 567 | 0.354 |
| 12 | 11.385 | recv | 1 | 309 | 0.063 |
| 13 | 11.385 | sent | 1 | 111 | 0.000 |
| 14 | 11.464 | recv | 1 | 124 | 0.079 |

### Prompt `list-1-to-20`

- t0_send: 0.000 s rel
- t_domdone: 32.865 s rel (stop gone + assistant length non-empty + stable ~3s)
- t_firstframe: 29.357 s rel
- t_lastframe: 29.612 s rel
- t0_to_firstframe (not counted as a mid-answer inter-frame gap; current-turn assistant length was still zero before the first frame): 29.357 s
- lastframe_to_domdone: 3.253 s
- max inter-frame mid-answer gap: 0.167 s

| # | t_rel_s | direction | opcode | payload_len_bytes | gap_since_prev_frame_s |
|---:|---:|---|---:|---:|---:|
| 1 | 29.357 | sent | 1 | 122 | n/a |
| 2 | 29.524 | recv | 1 | 17669 | 0.167 |
| 3 | 29.524 | sent | 1 | 112 | 0.000 |
| 4 | 29.612 | recv | 1 | 125 | 0.088 |

### Prompt `python-avg-6-lines`

- t0_send: 0.000 s rel
- t_domdone: 21.053 s rel (stop gone + assistant length non-empty + stable ~3s)
- t_firstframe: 2.363 s rel
- t_lastframe: 18.148 s rel
- t0_to_firstframe (not counted as a mid-answer inter-frame gap): 2.363 s
- lastframe_to_domdone: 2.905 s
- max inter-frame mid-answer gap: 4.989 s

| # | t_rel_s | direction | opcode | payload_len_bytes | gap_since_prev_frame_s |
|---:|---:|---|---:|---:|---:|
| 1 | 2.363 | recv | 1 | 180 | n/a |
| 2 | 7.123 | sent | 1 | 123 | 4.760 |
| 3 | 7.228 | recv | 1 | 7637 | 0.105 |
| 4 | 8.621 | recv | 1 | 1759 | 1.393 |
| 5 | 9.344 | recv | 1 | 1104 | 0.724 |
| 6 | 10.249 | recv | 1 | 180 | 0.904 |
| 7 | 12.431 | recv | 1 | 350 | 2.183 |
| 8 | 12.505 | recv | 1 | 2011 | 0.074 |
| 9 | 17.494 | recv | 1 | 2045 | 4.989 |
| 10 | 17.574 | recv | 1 | 1333 | 0.080 |
| 11 | 17.614 | recv | 1 | 2046 | 0.040 |
| 12 | 18.007 | recv | 1 | 350 | 0.393 |
| 13 | 18.011 | recv | 1 | 567 | 0.004 |
| 14 | 18.085 | recv | 1 | 309 | 0.074 |
| 15 | 18.085 | sent | 1 | 112 | 0.000 |
| 16 | 18.148 | recv | 1 | 125 | 0.063 |

## Rule validation

Rule tested: fire when no websocket frame for >= 8 s AND DOM stable (stop gone + assistant length non-empty + stable ~3s).

| prompt | max_mid_gap_s | simulated_fire_rel_s | added_latency_s | no_clip | no_false_early |
|---|---:|---:|---:|---|---|
| pong | 4.777 | 15.965 | 5.173 | true | true |
| one-sentence-ocean | 4.220 | 19.464 | 5.398 | true | true |
| list-1-to-20 | 0.167 | 37.612 | 4.747 | true | true |
| python-avg-6-lines | 4.989 | 26.148 | 5.095 | true | true |

Validation result: `PASS` — fires at/after each DOM turn-end and not during any recorded mid-answer inter-frame gap. Initial pre-first-frame silences are listed separately; the DOM gate was current-turn-aware (new assistant length non-empty), so those intervals did not satisfy the DOM-stable half of the rule.
