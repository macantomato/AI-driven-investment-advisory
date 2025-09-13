from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Advisor API")

# localhost for dev; cloudflare goes later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://*.pages.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)