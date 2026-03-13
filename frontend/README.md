# CTIC React Chat UI

Phase 3 frontend implementation for the CTIC Curriculum Engine.

## Stack

- React (Vite, JavaScript)
- Plain CSS
- Backend integration via environment variable

## Theme

- Primary: #FF9D28
- Secondary: #32336B
- Default background: white
- Optional dark mode toggle included

## Setup

1. Copy environment template:

   cp .env.example .env

2. Set backend base URL in .env:

   VITE_API_BASE_URL=http://localhost:8000

3. Install dependencies (if needed):

   npm install

4. Start dev server:

   npm run dev

## Features implemented

- Chat page with sidebar and conversation history
- New conversation button
- Message composer with Enter-to-send and Shift+Enter newline
- API call to POST /api/chat
- Activity result cards with external links
- Loading and error states
- Responsive layout for desktop and mobile
