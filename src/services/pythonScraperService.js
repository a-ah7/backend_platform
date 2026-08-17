const axios = require('axios');
const cheerio = require('cheerio');

const runPythonScraper = async (targetUrl) => {
  try {
    const { data } = await axios.get(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
      },
      timeout: 10000
    });
    const $ = cheerio.load(data);

    let domain = '';
    try {
      domain = new URL(targetUrl).hostname;
    } catch (e) {}

    // 1. العنوان والاسم
    const title =
      $('meta[property="og:title"]').attr('content') ||
      $('meta[name="twitter:title"]').attr('content') ||
      $('title').text().trim() ||
      'No title found.';

    // 2. الوصف
    const description =
      $('meta[property="og:description"]').attr('content') ||
      $('meta[name="twitter:description"]').attr('content') ||
      $('meta[name="description"]').attr('content') ||
      'No description found.';

    // 3. صورة Open Graph
    let og_image =
      $('meta[property="og:image"]').attr('content') ||
      $('meta[name="twitter:image"]').attr('content') ||
      $('img[src*="logo"]').attr('src') ||
      $('img[class*="logo"]').attr('src') ||
      $('img').first().attr('src') ||
      '';

    if (og_image && !og_image.startsWith('http')) {
      try {
        const origin = new URL(targetUrl).origin;
        og_image = new URL(og_image, origin).href;
      } catch (e) {}
    }

    // 4. الأيقونة (Favicon)
    let favicon =
      $('link[rel="apple-touch-icon"]').attr('href') ||
      $('link[rel="icon"]').attr('href') ||
      $('link[rel="shortcut icon"]').attr('href') ||
      '';

    if (favicon && !favicon.startsWith('http')) {
      try {
        const origin = new URL(targetUrl).origin;
        favicon = new URL(favicon, origin).href;
      } catch (e) {}
    }

    if (!favicon && domain) {
      favicon = `https://www.google.com/s2/favicons?domain=${domain}&sz=128`;
    }

    // 5. العنوان الجغرافي
    const address =
      $('meta[property="business:contact_data:street_address"]').attr('content') ||
      $('address').text().trim() ||
      'No address found.';

    const logoUrl = og_image || favicon || 'No logo found.';

    // إرجاع الكائن بالمسميات المطلوبة في السيرفر
    return {
      name: title,
      title: title,
      description: description,
      address: address,
      url: targetUrl,
      og_image: og_image || favicon,
      favicon: favicon,
      logo: logoUrl,
      keywords: [],
      social_links: [],
      phone: '',
      email: '',
      phones: [],
      emails: [],
      pages_scraped: []
    };
  } catch (error) {
    throw new Error('Failed to scrape website: ' + error.message);
  }
};

module.exports = {
  runPythonScraper
};