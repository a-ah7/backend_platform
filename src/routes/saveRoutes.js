const express = require("express");

const {
  saveScrapedData,
} = require("../controllers/saveController");

const router = express.Router();

router.post("/", saveScrapedData);

module.exports = router;