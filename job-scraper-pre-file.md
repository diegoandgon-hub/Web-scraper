# Job Scraper PRD - Pre-File Instructions

## Project Overview
Build a web scraper to find entry-level engineering positions in the French part of Switzerland (Romandie region).

## Target Job Criteria

### Engineering Disciplines
- Process Engineering
- Automation Engineering
- Energy Engineering

### Geographic Scope
- **Region**: French-speaking Switzerland (Romandie)
- **Key cantons**: Geneva (GE), Vaud (VD), Valais (VS), Neuchâtel (NE), Jura (JU), Fribourg (FR)
- **Major cities**: Geneva, Lausanne, Sion, Neuchâtel, Fribourg

### Language Requirements
- **MANDATORY**: Position must be fully in English
- **DISCARD IF**: Job requires French or German language skills
- **Filter logic**: Exclude any posting mentioning French/German as required or preferred

### Experience Level
- Entry-level positions (0-2 years experience)
- Recent graduates
- Internships that DO NOT require current university enrollment
- Post-graduation internships acceptable

### Position Type
- Internships (not requiring concurrent university enrollment)
- Graduate programs
- Junior/Entry-level full-time positions
- Trainee positions

## Technical Requirements to Define in PRD

### Data Sources to Consider
- Job boards specific to Switzerland (jobs.ch, jobup.ch, etc.)
- International job boards with Switzerland filters (LinkedIn, Indeed, Glassdoor)
- Company career pages (ABB, Nestlé, Novartis, Roche, etc.)
- University career portals (EPFL, UNIGE, etc.)

### Key Data Fields to Scrape
- Job title
- Company name
- Location (city/canton)
- Job description
- Required qualifications
- Language requirements
- Experience level
- Application deadline
- Application URL
- Date posted

### Filtering Logic
1. **Geographic filter**: Must be in Romandie cantons
2. **Language filter**: Must be English-only (no French/German required)
3. **Experience filter**: Entry-level, graduate, or internship
4. **Discipline filter**: Must match process/automation/energy engineering keywords
5. **Enrollment filter**: Exclude internships requiring active university enrollment

### Output Requirements
- Structured data format (JSON/CSV)
- Duplicate detection
- Date of scraping
- Source URL for each job
- Flagged jobs that meet all criteria

## Implementation Considerations for PRD

### Scraping Strategy
- Define scraping frequency (daily, weekly)
- Handle anti-scraping measures (rate limiting, rotating user agents)
- Error handling and logging
- Data validation

### Storage
- Database schema design
- Historical data retention
- Update mechanism for existing listings

### Compliance
- Respect robots.txt
- Terms of service compliance for each source
- GDPR considerations (minimal data collection)

### Deliverables
- Scraper codebase
- Configuration files
- Documentation
- Sample output data
- Scheduling/automation setup

## Success Metrics
- Number of relevant jobs found per week
- Accuracy of filtering (% of results meeting all criteria)
- Data freshness (time between posting and detection)
- Coverage across target companies and regions

## Future Enhancements (Phase 2)
- Email notifications for new matching positions
- ML-based job description analysis
- Salary range extraction
- Application deadline reminders
- Company research integration

---

## Notes for PRD Development
- Include specific Swiss job board APIs if available
- Define fallback strategies if primary sources fail
- Consider legal/ethical implications of scraping
- Plan for maintenance and updates to scrapers as websites change
