const express = require("express");

const {
  startScraping,
} = require("../controllers/scrapingController");

const router = express.Router();

router.post("/", startScraping);

module.exports = router;