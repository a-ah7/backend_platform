require("dotenv").config();
const express = require("express");
const cors = require("cors");

const app = express();

app.use(cors());
app.use(express.json());

const scrapingRoutes = require("./routes/scrapingRoutes");
const healthRoutes = require("./routes/healthRoutes");
const itemsRoutes = require("./routes/itemsRoutes");

app.use("/api/scrape", scrapingRoutes);
app.use("/api/health", healthRoutes);
app.use("/api/items", itemsRoutes);

const PORT = process.env.PORT || 3000;

app.listen(PORT, "0.0.0.0", () => {
  console.log("Server running on port " + PORT);
});