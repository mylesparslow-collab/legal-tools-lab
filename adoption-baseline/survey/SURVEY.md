# AI tool use: short survey

Printable copy of `survey.json`, version 1.0. Personal portfolio demo with synthetic practice and office names.

This survey asks how you use the firm's approved AI assistants. It has 14 questions and takes under five minutes. It does not ask for your name. Results are reported for groups of five or more people only. There are no right answers, and not using the tools is a useful answer.

**1. What is your role?**

- ( ) Partner
- ( ) Counsel
- ( ) Associate
- ( ) Paralegal
- ( ) Business services or other staff

**2. Which practice do you mainly work in?**

- ( ) Banking and finance
- ( ) Competition
- ( ) Corporate
- ( ) Disputes
- ( ) Employment
- ( ) Intellectual property
- ( ) Private client
- ( ) Real estate
- ( ) Regulatory
- ( ) Tax

**3. Which office are you based in?**

- ( ) Eastfield
- ( ) Harbour Quay
- ( ) Lakeshore
- ( ) Midvale
- ( ) Northgate
- ( ) Riverside
- ( ) Southmere
- ( ) Westbrook

**4. In the last 7 days, which of these did you use for work? Select all that apply.**

- [ ] Assistant A
- [ ] Assistant B
- [ ] Another AI tool
- [ ] None of these

**5. In the last 30 days, which of these did you use for work? Select all that apply.**

- [ ] Assistant A
- [ ] Assistant B
- [ ] Another AI tool
- [ ] None of these

**6. In a typical working week, on how many days do you use an AI assistant for work?**

- ( ) No days
- ( ) 1 day
- ( ) 2 to 3 days
- ( ) 4 to 5 days

**7. In the last 30 days, which kinds of task did you use an AI assistant for? Select all that apply.**

- [ ] Drafting
- [ ] Summarising
- [ ] Research
- [ ] Reviewing documents
- [ ] Email
- [ ] Chronologies or timelines
- [ ] Other
- [ ] I did not use one

**8. In the last 30 days, where did AI-assisted output go? Select all that apply.**

- [ ] Internal use only
- [ ] Work product sent to a client
- [ ] A document filed with a court or tribunal
- [ ] Not applicable

**9. How often do you check AI-assisted output before relying on it?**

- ( ) Always
- ( ) Usually
- ( ) Sometimes
- ( ) Rarely
- ( ) Never
- ( ) Not applicable

**10. When you check output, what do you do? Select all that apply.**

- [ ] Read it in full
- [ ] Compare it with the source documents
- [ ] Look up each citation or reference
- [ ] Ask a colleague to review it
- [ ] Something else
- [ ] I do not check it
- [ ] Not applicable

**11. Does anything limit your use of the approved AI assistants? Select all that apply.**

- [ ] I am not confident the output is accurate
- [ ] I have not had training
- [ ] Client instructions restrict it
- [ ] I am not sure what is allowed
- [ ] I have not had time to try them
- [ ] My work does not suit them
- [ ] Something else
- [ ] Nothing limits my use

**12. How confident are you that you know what the firm allows you to do with these tools?**

- ( ) 1 - Not at all confident
- ( ) 2
- ( ) 3
- ( ) 4
- ( ) 5 - Very confident

**13. How confident are you in getting useful results from these tools?**

- ( ) 1 - Not at all confident
- ( ) 2
- ( ) 3
- ( ) 4
- ( ) 5 - Very confident

**14. Is there anything else you would like to say about using AI tools in your work? Please do not name clients, matters or colleagues.** (optional)

_Free text._

## Design choices

- Short on purpose: 14 questions, mostly tick boxes, under five minutes. Longer surveys lose the
  people who use the tools least, which are the people this baseline most needs to hear from.
- No name or email is collected. Role, practice and office are asked so results can be grouped.
  Groups under five people are not reported.
- Two fixed recall windows (7 days and 30 days) are asked before the "typical week" question.
  A fixed window can be compared with the usage logs for the same week. "Typical" cannot.
- Wording is neutral. Questions do not assume the tools are useful or that people should be
  using them. "None", "Not applicable" and "Nothing limits my use" are always offered.
- The checking question asks what people do, not whether they follow a policy.
- "Another AI tool" is offered without comment so that use outside the approved tools can be
  seen in aggregate. Expect it to be under-reported.
- The blocker list is the hypothesis list from the plan. "Something else" and the free-text
  question are there for what the list misses. Option order should be shuffled if the survey
  platform supports it.
- Free-text answers are counted in the report but not reproduced.

## Known biases

- Self-report inflates use. People recall more use than the logs show, and some answer with what
  they think is expected. The report shows survey and log figures side by side for the same
  group and week so the size of the gap is visible.
- Non-response. People who use the tools are more likely to answer a survey about them. The
  response count is shown next to every survey figure. Survey figures describe respondents,
  not the firm.
- The survey is anonymous, so respondents are not matched to log records. The survey-versus-log
  gap compares two group rates. It cannot say who over- or under-reported.
- The logs only cover the approved tools. The survey is the only source for other tools, and
  it is a weak one.
- Role, practice and office are self-described and may differ from the roster.
