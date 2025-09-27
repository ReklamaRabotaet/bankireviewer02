# Overview

This is a web scraping project designed to collect and analyze customer reviews from banki.ru, a Russian banking website. The scraper targets multiple banks (Sberbank, VTB, Alfa-Bank, Dom.rf) and extracts review data including ratings, text content, and metadata. The project focuses on efficient data collection through direct API calls rather than browser automation, with built-in anti-blocking mechanisms and resumable operation capabilities.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Core Components

**Data Collection Engine**: The main scraping functionality is built around direct HTTP requests to banki.ru's internal AJAX API endpoints. This approach bypasses the need for browser automation tools like Selenium, resulting in significantly faster data collection.

**Anti-Blocking System**: Implements multiple strategies to avoid detection and blocking:
- User-agent rotation from a predefined list of common browser signatures
- Random delays between requests to simulate human browsing patterns
- Cookie refresh mechanisms to maintain session validity
- Proxy support for IP rotation

**Resume Capability**: The scraper includes intelligent resume functionality that detects previously scraped data and continues from the last successful page. This is implemented using pandas to analyze existing CSV files and calculate the appropriate starting point.

**Multi-Bank Support**: Configured to handle multiple banking institutions with a centralized configuration system that defines bank codes, names, and output file mappings.

**Service Category Filtering**: Supports filtering reviews by banking service categories including deposits, credits, cards, mortgage, and business services.

## Data Architecture

**Storage Format**: All scraped data is stored in CSV format with structured columns for review metadata, ratings, text content, and timestamps.

**Data Validation**: Uses pandas for data parsing and validation when resuming operations, with error handling for corrupted or empty files.

**Metadata Tracking**: Maintains separate JSON files to track scraping progress, including last processed page numbers and timestamps.

## Configuration Management

**JSON-Based Config**: Uses a simple JSON configuration file for proxy settings and operational parameters.

**Environment Isolation**: Designed to work with `uv` package manager for Python environment management and dependency isolation.

# External Dependencies

**HTTP Library**: Uses the `requests` library for making HTTP calls to banki.ru's API endpoints.

**Data Processing**: Relies on `pandas` for CSV file operations, data analysis, and resume logic implementation.

**Web Framework**: Flask for the dashboard web application with gunicorn for production deployment.

**ML Integration**: API endpoints configured for Zero-Shot Classification model integration with BERT.

**Proxy Services**: Configured to work with external proxy services for IP rotation and geographic distribution of requests.

**Target Website**: Integrates with banki.ru's internal AJAX API endpoints that power their review pagination system.

**Python Runtime**: Requires Python environment with standard libraries including `csv`, `json`, `time`, `random`, `os`, `math`, and `datetime`.

# Recent Updates (September 27, 2025)

**Dashboard Implementation**: Created Flask web application with ML API integration ready for hackathon demonstration.

**ML Dataset Preparation**: Generated 165 training examples across 11 categories for Zero-Shot Classification model training.

**Deployment Configuration**: Set up production-ready deployment with gunicorn, health checks, and proper dependency management.

**API Schema**: Implemented ML API endpoints following JSON request/response pattern for sentiment analysis and category classification.

**UI/UX Improvements**: Completed all 8 UI enhancement tasks including Russian localization, Gazprombank branding, period selection controls, and font integration.

**GitHub Preparation**: Created comprehensive documentation (README.md, ML_API_CONTRACT.md) for repository publication as "gpb-reviewer" for ML engineer collaboration. API contract follows hackathon specifications with ~250 review JSON format, 3-minute timeout, and proper error handling with fallback values.

# GitHub Publication Status

**Repository Name**: gpb-reviewer
**Purpose**: Collaboration with ML engineer for ЛЦТ Хакатон demonstration
**Documentation**: Complete with setup instructions, API contract, and technical specifications
**ML Integration**: Ready for private GitHub ML model connection via POST /api/analyze endpoint