# SSRF Link Preview Lab — Speaker Script

The cues in square brackets indicate when to advance the slide animation.

## Slide 1 — SSRF Link Preview Lab

Good evening, everyone.

Our project is S-S-R-F Link Preview Lab, a controlled testbed for comparing attacks and defenses in link preview services.

## Slide 2 — Link Previews in Everyday Use

Link previews are something we use every day.

[Click]

A link in a chat becomes a card like this.

[Click]

The browser sends the URL to a preview service. The service fetches the page and returns the card.

[Click]

The server is now fetching a URL chosen by the user.

## Slide 3 — Link Preview as a Network Boundary

Now let us look at the preview service as a network boundary.

[Click]

In normal use, the browser submits a URL, and the preview service fetches a public page. This is the expected behavior.

[Click]

Now suppose there is an internal report inside the private network. The user cannot access this report directly, so the direct request is blocked.

[Click]

However, the preview service is already inside that network. If the user can make the service request the internal report, the user can reach something that should have remained private.

[Click]

A documented vulnerability in Synology Chat allowed authenticated users to use link previews to access intranet resources.

[Click]

A natural defense is to check the URL before fetching it. But is checking the submitted URL enough to control every connection that follows?

## Slide 4 — URL Approval Does Not Equal Connection Identity

Checking only the submitted URL is not enough, because the destination can change after that check. Here are two ways this can happen.

[Click]

First, consider an HTTP redirect.

[Click twice]

The attacker submits a public URL, so the initial check allows it. The preview service then requests the public redirect server.

[Click]

The server now redirects the request to the internal report.

[Click twice]

If the preview service follows this redirect without checking the new URL, it reaches the private resource and returns its content to the attacker.

[Click]

The second method is DNS rebinding.

[Click three times]

This time, the URL does not change. The attacker submits a domain name, and its first DNS response gives a public address. That address passes the policy check.

[Click twice]

Later, when the service opens the connection, the same domain is resolved again. The attacker now returns a private address.

[Click twice]

The request reaches the internal report, and the report preview is returned to the attacker. Whether this works in practice depends on DNS caching and client behavior, but the checked address and the connected address can be different.

[Click]

In both cases, the destination changes after it has been approved. A redirect changes the URL, while DNS rebinding changes the address behind the same URL.

## Slide 5 — Can We Block Private Access Without Breaking Public Previews?

This leads to our main research question: can we block private access without breaking normal public previews?

[Click]

For security, the report must not be reached or disclosed.

[Click]

For utility, legitimate direct and redirected previews must still work.

[Click]

So a useful defense must satisfy both goals: it must block private access while keeping normal previews useful.

## Slide 6 — What Did This Project Contribute?

Guided by CWE-918 and OWASP, we make three contributions.

[Click]

First, a controlled testbed for redirect and DNS attacks.

[Click]

Second, five policies in the same preview pipeline.

[Click]

Third, trial-linked records of decisions, DNS answers, connected peers, and destination events.

[Click]

Together, they support safe reproduction and fair comparison.

## Slide 7 — Our Threat Model

Before presenting our defense, we need to define our threat model. The attacker is a normal user who is allowed to submit URLs. The preview service and the internal report are trusted, which means the attacker cannot modify them.

[Click]

The user cannot reach the report, but the preview service can.

[Click]

The attacker controls the URL, redirects, and DNS for their domain.

[Click]

Their goal is an unauthorized request to the report.

[Click]

A request reaching the report counts as an attack. Its marker returning counts as disclosure.

[Click]

This is indirect access through a trusted service.

## Slide 8 — Every Connection Must Follow Its Destination Check

Our central principle is that a check must control the connection.

[Click]

For redirects, we check every new URL.

[Click]

For DNS, we bind libcurl to the approved IP. Together, these rules form Check and Bind.

[Click]

Validation must constrain the actual connection.

## Slide 9 — How Is the Testbed Designed?

Here are three design choices that make its experiments safe and comparable.

[Click]

Synthetic targets are isolated in Docker, so attacks are safe to repeat.

[Click]

Only the policy changes; the preview pipeline stays the same.

[Click]

Trial IDs connect service records with independent destination records.

[Click]

Now, let us demonstrate the testbed through its Web UI.

## Slide 10 — How Did We Evaluate the Defenses?

For the evaluation, we compared five policies in controlled batch experiments.

No Check performs no destination validation. Initial URL checks only the submitted URL. Each Hop checks every redirected URL. Check and Bind also binds the connection to the checked IP. No Redirects refuses to follow redirects.

We ran every policy 50 times for each HTTP scenario.

[Click]

Normal tests covered direct pages and one or three redirects. Across 750 trials, we measured success and latency.

[Click]

Attack tests covered direct internal targets and redirects. Across 1,000 trials, we measured report access and disclosure.

[Click]

Four DNS traces linked answers, connected peers, and report events. They show the mechanism, not an attack rate.

[Click]

This covers both security and preview utility.

## Slide 11 — How Did the Five Policies Perform?

Here are the results. In the first two rows, the number shows how often the internal report was reached, so zero is the safe result. Each row combines two scenarios, with 50 trials for each scenario and policy.

[Click]

For direct targets, No Check scored 100. Every checking policy scored zero.

[Click]

With redirects, Initial URL scored 100. The remaining three policies scored zero.

[Click]

In the matched DNS probe, Each Hop connected internally; Check and Bind stayed external.

[Click]

For normal previews, the first four scored 150; No Redirects scored 50.

[Click]

Check and Bind blocked 200 HTTP attacks, preserved 150 previews, and added 1.2 milliseconds to median latency.

[Click]

It gave the best security and utility balance.

## Slide 12 — Where the Evidence Stops

These results have three main limits.

[Click]

First, our repeated HTTP experiments cover direct requests and chains of one or three redirects. They do not tell us what happens with longer chains, different hosts, or protocol changes.

[Click]

Second, our DNS evidence contains only four individual probes, so we cannot report a general attack success rate.

In the TTL-one probe with a primed cache, Each Hop stayed on the external address, and the attack did not reach the report. This single observation shows that cache and TTL conditions can change the outcome, but it is not a general conclusion.

[Click]

Third, we evaluated one Python and PycURL client stack using selected IPv4 and HTTP scenarios. We did not evaluate HTTPS, IPv6, other HTTP clients, or production network controls.

[Click]

Our conclusions apply only to these tested conditions.

## Slide 13 — Next Steps

These limits define our next steps.

[Click]

First, test longer, cross-host, and HTTPS redirect chains.

[Click]

Second, repeat DNS trials across TTL and cache conditions.

[Click]

Third, test IPv6, more URL formats, and other clients.

[Click]

These experiments should remain inside a controlled environment.

## Slide 14 — What Did We Learn?

Finally, let us answer our research question.

[Click]

Within our tests, Check and Bind blocked both attacks and preserved every normal preview.

[Click]

Zero of 200 HTTP attacks reached the report, the matched DNS probe stayed external, and all 150 normal previews succeeded.

[Click]

The broader lesson is that validation must constrain the executed action.

## Slide 15 — Thank You

That concludes our presentation. Thank you.
