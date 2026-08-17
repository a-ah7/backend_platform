const axios = require('axios');
const cheerio = require('cheerio');

const runPythonScraper = async (targetUrl) => {
  try {
    const { data } = await axios.get(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
      },
      timeout: 10000
    });
    const $ = cheerio.load(data);

    // 1. جلب العنوان (مباشر أو من OpenGraph/Twitter)
    const title =
      $('meta[property="og:title"]').attr('content') ||
      $('meta[name="twitter:title"]').attr('content') ||
      $('title').text().trim() ||
      'No title found.';

    // 2. جلب الوصف
    const description =
      $('meta[property="og:description"]').attr('content') ||
      $('meta[name="twitter:description"]').attr('content') ||
      $('meta[name="description"]').attr('content') ||
      'No description found.';

    // 3. جلب الصورة أو اللوجو مع تحويل الرابط إلى رابط كامل
    let logo =
      $('meta[property="og:image"]').attr('content') ||
      $('meta[name="twitter:image"]').attr('content') ||
      $('link[rel="apple-touch-icon"]').attr('href') ||
      $('link[rel="icon"]').attr('href') ||
      $('link[rel="shortcut icon"]').attr('href') ||
      $('img').first().attr('src') ||
      'No logo found.';

    if (logo && logo !== 'No logo found.' && !logo.startsWith('http')) {
      try {
        const origin = new URL(targetUrl).origin;
        logo = new URL(logo, origin).href;
      } catch (e) {}
    }

    // 4. جلب العنوان أو العنوان البريدي
    const address =
      $('meta[property="business:contact_data:street_address"]').attr('content') ||
      $('address').text().trim() ||
      'No address found.';

    return { title, description, logo, address };
  } catch (error) {
    throw new Error('Failed to scrape website: ' + error.message);
  }
};

module.exports = {
  runPythonScraper
};