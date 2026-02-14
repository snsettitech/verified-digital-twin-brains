# Public Simulator Walkthrough

- Executed at: Sat, 14 Feb 2026 22:13:16 GMT
- Frontend: http://127.0.0.1:3000
- Backend: http://127.0.0.1:8000
- Simulator URL: http://127.0.0.1:3000/dashboard/simulator/public?twin_id=cb977b10-ece4-4a0c-8d4d-bc1ddad58284&share_token=h1mewxxvgqk
- Twin ID: cb977b10-ece4-4a0c-8d4d-bc1ddad58284
- Share token: h1me...vgqk
- Screenshot: `tmp\public_simulator_walkthrough.png`

## Before (Direct Public API `/public/chat/{twin}/{token}`)
- `hi` -> status 200, confidence=0.0, citations=0, endpoint=`/public/chat/cb977b10-ece4-4a0c-8d4d-bc1ddad58284/h1mewxxvgqk`
  - assistant: "Hi there! How can I assist you today? What would you like to discuss?"
- `who are you?` -> status 200, confidence=0.0, citations=0, endpoint=`/public/chat/cb977b10-ece4-4a0c-8d4d-bc1ddad58284/h1mewxxvgqk`
  - assistant: "I'm your AI digital twin, here to help with coaching and provide answers based on your own knowledge. What would you like to talk about?"
- `do you know antler` -> status 200, confidence=0.0, citations=1, endpoint=`/public/chat/cb977b10-ece4-4a0c-8d4d-bc1ddad58284/h1mewxxvgqk`
  - assistant: "Antler seems to be involved in supporting founders, especially when it comes to scaling their businesses from the early stage to gaining market traction. They appear to offer resources like strategy development and investor relations, but I'd need more information to provide specific details."

## After (UI on `/dashboard/simulator/public`)
- `hi` -> status 200, endpoint_type=public_chat, confidence=0.0, citations=0, queued=False
  - endpoint: `http://127.0.0.1:8000/public/chat/cb977b10-ece4-4a0c-8d4d-bc1ddad58284/h1mewxxvgqk`
  - assistant: "Hi there! How can I assist you today? What would you like to discuss?"
- `who are you?` -> status 200, endpoint_type=public_chat, confidence=0.0, citations=0, queued=False
  - endpoint: `http://127.0.0.1:8000/public/chat/cb977b10-ece4-4a0c-8d4d-bc1ddad58284/h1mewxxvgqk`
  - assistant: "I'm your AI digital twin, here to help with coaching and provide answers based on your knowledge. I can offer guidance and support whenever you need it. What would you like to talk about?"
- `do you know antler` -> status 200, endpoint_type=public_chat, confidence=0.0, citations=1, queued=False
  - endpoint: `http://127.0.0.1:8000/public/chat/cb977b10-ece4-4a0c-8d4d-bc1ddad58284/h1mewxxvgqk`
  - assistant: "Antler is indeed involved in supporting founders, especially in early-stage companies, and helping them scale to achieve market traction. They seem to work with investors, founders, and are involved in global market expansion, as noted in reference 47f5e645-0c5e-42c0-8ed1-be6f5c7ffeb6. I'm fairly confident in this information, but if you have more context, I'd be happy to try and provide more details."
