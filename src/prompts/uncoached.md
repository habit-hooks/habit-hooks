General guidance: the issues listed are code smells. They tell you that there is likely something wrong with the code. Follow these steps:
- Ask yourself why the rule exists in the first place. What is it telling you about the code?
- Find a fix that improves maintainability, cuts cruft — doing the same with fewer statements where that lowers cognitive load — and/or improves security, scalability, and resilience.
- AVOID AT ALL COST: any fix that is designed to appease the reporting tool, but goes against the spirit of the warning.