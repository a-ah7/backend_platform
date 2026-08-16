const express = require("express");

const {
  saveScrapedData,
} = require("../controllers/SaveController");

const router = express.Router();

router.post("/", saveScrapedData);

module.exports = router;