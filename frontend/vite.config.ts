import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// `npm run dev` serves the desk at http://localhost:5173 and opens it in the browser.
// The page calls the FastAPI backend directly at http://localhost:8000 (CORS allows 5173).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    open: true,
  },
})
