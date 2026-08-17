const axios = require('axios');
const cheerio = require('cheerio');

const runPythonScraper = async (targetUrl) => {
  try {
    const { data } = await axios.get(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    });
    const $ = cheerio.load(data);

    return {
      title: $('title').text().trim() || 'No title found.',
      description: $('meta[name="description"]').attr('content') || 'No description found.',
      logo: $('link[rel="icon"]').attr('href') || $('img').first().attr('src') || 'No logo found.',
      address: $('address').text().trim() || 'No address found.'
    };
  } catch (error) {
    throw new Error('Failed to scrape website: ' + error.message);
  }
};

module.exports = {
  runPythonScraper
};