---
name: Design Proposal
about: Propose a design before writing code
title: "[R?] Design Proposal: "
labels: design-proposal
assignees: ''
---

## Design Proposal

**Track**: R[1-5]  
**Component(s) affected**: [exact file paths]

### Problem
[What's missing, broken, or needed. Be specific.]

### Proposed Solution
[Your technical approach. Include:]
- Which files you will ADD, MODIFY, or DELETE
- Which Pydantic models or contracts change
- Which tests you will add

### Contract Changes
[If your change modifies any shared contract (BridgeConfig, IngestionRecord, 
MCPManifest, filesystem paths), list the EXACT before/after.]

[If no contract changes, write "None".]

### Files You Will NOT Touch
[Explicitly list components outside your track that you will not modify.]

### Estimated Test Count
[How many new tests? What does each one prove?]

### Checklist
- [ ] I have read CONTRIBUTING.md
- [ ] My change stays within one track
- [ ] I am not modifying frozen contract models without approval
- [ ] I will not commit __pycache__ or .pyc files
