// backend/app/pipeline/reduce_pass.py's TQ_FACTOR_WEIGHTS — kept in sync manually
// since the weights are hardcoded Python constants, not served by the API (same
// pattern as GoNoGoCard.tsx's own FACTOR_WEIGHTS for the 8-factor score).
export const TQ_FACTOR_WEIGHTS: Record<string, number> = {
  "Similar Project Experience": 20,
  "Government/PSU Project Experience": 10,
  "Relevant Industry 4.0/AI/ML Experience": 10,
  "Technical Solution/Methodology": 15,
  "Understanding of Requirements": 10,
  "Proposed Architecture/Solution Design": 5,
  "Key Personnel": 10,
  "Technology Capability": 5,
  "Implementation Methodology": 5,
  "Project Management Approach": 5,
  "Support/O&M Approach": 3,
  "Innovation/Value Addition": 2,
};
