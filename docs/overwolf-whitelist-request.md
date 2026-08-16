# Overwolf developer access (R-016)

## What the research found

Whitelisting is not a free-text email in the way community write-ups suggest.
Overwolf's own documentation says:

> "Using Overwolf's APIs require your app idea to be whitelisted. This is only
> given to app ideas submitted and approved using the App proposal process."

and, decisively for this project:

> "Overwolf currently doesn't approve private apps."

The proposal process expects a **public** app with at least one visible desktop
window, compliant monetisation (ads or subscriptions), and compliance with both
Overwolf's terms and the game's policies.

That is a policy obstacle, not a paperwork one. This project is a personal tool
with no store ambitions, so on the documented rules it does not qualify.

**We do not dress it up as a public app to get through the proposal form.**
Obtaining access by misrepresenting what the software is would be deceiving a
company to get onto its platform, and the access would be withdrawn the moment
the real purpose surfaced - after the project had been built on top of it.

So the approach is a short, direct question that gets a fast yes/no, rather than
a proposal engineered to pass.

---

## The email

**To:** developers@overwolf.com
**Subject:** Development-only whitelist for a personal PUBG project?

Hi,

I'm building a personal project on top of the PUBG Game Events Provider and I'd
like to load it unpacked on my own machine for development. Before I go further
I want to check whether that's possible at all, because your docs say
whitelisting comes from the App proposal process and that private apps aren't
approved.

The app itself is small: a background app that registers five documented GEP
features (`location`, `me`, `phase`, `map`, `match_info`) and forwards them to a
local process on 127.0.0.1. It requests only the `GameInfo` permission, makes no
external network calls, and isn't intended for the store.

To be upfront about what it's for: it feeds a personal experiment that replays a
manually recorded route in PUBG **Training Mode**, using ordinary OS keyboard and
mouse input. Training Mode only, never public matches. No combat features - I
deliberately don't request `kill`, `death`, `killer`, `team` or `roster` - and no
memory reading, injection or anti-cheat interference.

Is there any development-only access for something like this, or is a public
store app the only route? A straight no is genuinely useful - I'd rather know
now than build further on access I can't have.

Thanks,
[your name]
[your Overwolf account email]

---

## If the answer is no

That is a feasibility gate, and the project stops at it rather than routing
around it - the same rule that applies if PUBG rejects ordinary input at
Stage 3. Record the reply in `docs/decisions.md` and mark R-016 realised.

The only fallback that stays inside the declared scope would be deriving
position from **visible pixels** instead of game events, since the scope permits
"visible game pixels". That would be a different project shape: no `location`
feature, so position would have to come from the in-game map or minimap, with
accuracy far worse than the ~1 Hz coordinate stream this design assumes. It is
not a drop-in substitute and should not be started speculatively.
