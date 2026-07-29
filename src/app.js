const express = require("express");
const cors = require("cors");

const healthRoutes = require("./routes/healthRoutes");
const itemsRoutes = require("./routes/itemsRoutes");
const scrapingRoutes = require("./routes/scrapingRoutes");
const saveRoutes = require("./routes/saveRoutes");

const app = express();

app.use(cors());
app.use(express.json());

app.use("/api/health", healthRoutes);
app.use("/api/items", itemsRoutes);

app.use("/api/scrape", scrapingRoutes);
app.use("/api/save", saveRoutes);

module.exports = app;