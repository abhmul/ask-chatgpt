# M-006 T3-diag readiness diagnostic

MESSAGES_USED: 0

## Readiness timeline

target_s | actual_s | #prompt-textarea | main:has(#prompt-textarea) | main | send-button | New-chat
---: | ---: | ---: | ---: | ---: | ---: | ---:
0 | 0.00 | 0 | 0 | 1 | 1 | 0
1 | 1.00 | 1 | 1 | 1 | 0 | 1
2 | 9.92 | 1 | 1 | 1 | 0 | 1
3 | 10.59 | 1 | 1 | 1 | 0 | 1
5 | 10.62 | 1 | 1 | 1 | 0 | 1
8 | 10.63 | 1 | 1 | 1 | 0 | 1
12 | 12.00 | 1 | 1 | 1 | 0 | 1

First present: #prompt-textarea=1s; main:has(#prompt-textarea)=1s; main=0s; button[data-testid=send-button]=0s; a[aria-label=New chat]=1s

## Page state

- title: 'ChatGPT'
- url path-shape: /
- auth/login shape: False
- Cloudflare marker present: False (iframe[src*=challenges.cloudflare.com]=0, #challenge-running=0; title_just_a_moment=False)
- login selector counts: a[href*=auth/login]=0, button:has-text(Log in)=0, button:has-text(Sign up)=0

## Overlays/interstitials

- overlay selector counts: #onetrust-banner-sdk=0, [aria-modal=true]=0, [role=dialog]=0, button:has-text(Stay logged out)=0, [data-testid*=modal i]=1, [data-testid*=onboarding i]=0, [data-testid*=cookie i]=0
- #prompt-textarea coverage: present; covered=False; top_kind=p

## New-chat observation

- action: clicked a[aria-label='New chat'] on own tab (0 send)
- result: click completed
- url path-shape after New chat: /
- #prompt-textarea after New chat: 1

## Tab hygiene self-check

- preexisting tabs recorded: 1
- preexisting tabs still present at end: 1/1
- closed only own tab: True
- browser.close()/context.close() called: no

DIAGNOSIS: hydration-timing 1 s. MESSAGES_USED: 0
T3-diag-STATUS: DONE
