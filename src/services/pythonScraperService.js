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

    let title = '';
    let description = '';
    let logo = '';
    let address = '';

    // 1. قراءة البيانات المهيكلة JSON-LD (التي تستخدمها المواقع الحديثة للوجو والعنوان)
    $('script[type="application/ld+json"]').each((_, element) => {
      try {
        const json = JSON.parse($(element).html());
        const item = Array.isArray(json) ? json[0] : json;

        if (item) {
          if (!logo && item.logo) {
            logo = typeof item.logo === 'string' ? item.logo : item.logo.url;
          }
          if (!address && item.address) {
            if (typeof item.address === 'string') {
              address = item.address;
            } else if (typeof item.address === 'object') {
              address = [item.address.streetAddress, item.address.addressLocality, item.address.addressCountry].filter(Boolean).join(', ');
            }
          }
          if (!description && item.description) description = item.description;
          if (!title && item.name) title = item.name;
        }
      } catch (e) {}
    });

    // 2. إذا لم نجد العنوان والوصف في JSON-LD، نأخذها من الميتا تاجز
    if (!title) {
      title =
        $('meta[property="og:title"]').attr('content') ||
        $('meta[name="twitter:title"]').attr('content') ||
        $('title').text().trim() ||
        'No title found.';
    }

    if (!description) {
      description =
        $('meta[property="og:description"]').attr('content') ||
        $('meta[name="twitter:description"]').attr('content') ||
        $('meta[name="description"]').attr('content') ||
        'No description found.';
    }

    // 3. البحث عن اللوجو بوسوم الصور والأيقونات
    if (!logo) {
      logo =
        $('meta[property="og:image"]').attr('content') ||
        $('meta[name="twitter:image"]').attr('content') ||
        $('link[rel="apple-touch-icon"]').attr('href') ||
        $('link[rel="icon"]').attr('href') ||
        $('img[src*="logo"]').attr('src') ||
        $('img[class*="logo"]').attr('src') ||
        $('img[alt*="logo"]').attr('src') ||
        $('img').first().attr('src');
    }

    // تحويل رابط اللوجو إلى رابط كامل إذا كان نسبياً
    if (logo && !logo.startsWith('http')) {
      try {
        const origin = new URL(targetUrl).origin;
        logo = new URL(logo, origin).href;
      } catch (e) {}
    }

    // بديل مضمون للوجو عبر غوغل إذا لم يجد الكود أي صورة
    if (!logo) {
      try {
        const domain = new URL(targetUrl).hostname;
        logo = `https://www.google.com/s2/favicons?domain=${domain}&sz=128`;
      } catch (e) {
        logo = 'No logo found.';
      }
    }

    // 4. البحث عن العنوان الإضافي
    if (!address) {
      address =
        $('meta[property="business:contact_data:street_address"]').attr('content') ||
        $('address').text().trim() ||
        'No address found.';
    }

    return { title, description, logo, address };
  } catch (error) {
    throw new Error('Failed to scrape website: ' + error.message);
  }
};

module.exports = {
  runPythonScraper
};