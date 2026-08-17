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
    const htmlContent = $.html();
    const bodyText = $('body').text();

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

    // 3. الصورة واللوجو
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

    // 4. الكلمات المفتاحية (Keywords) مع استخراج تلقائي
    let keywords = [];
    const keywordsMeta = $('meta[name="keywords"]').attr('content');

    if (keywordsMeta) {
      keywords = keywordsMeta.split(',').map(k => k.trim()).filter(Boolean);
    } else {
      const sampleText = (`${title} ${description} ` + $('h1, h2').text())
        .toLowerCase()
        .replace(/[^a-zA-Z0-9\u0600-\u06FF\s]/g, '');

      const stopWords = new Set([
        'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 
        'is', 'are', 'was', 'were', 'be', 'this', 'that', 'from', 'as', 'it', 'your', 'you',
        'no', 'found', 'title', 'description', 'official', 'site', 'online'
      ]);

      const wordCounts = {};
      sampleText.split(/\s+/).forEach(word => {
        if (word.length > 3 && !stopWords.has(word)) {
          wordCounts[word] = (wordCounts[word] || 0) + 1;
        }
      });

      keywords = Object.keys(wordCounts)
        .sort((a, b) => wordCounts[b] - wordCounts[a])
        .slice(0, 8);
    }

    // 5. استخراج الإيميلات (Emails)
    const emailSet = new Set();
    $('a[href^="mailto:"]').each((_, el) => {
      const mail = $(el).attr('href').replace('mailto:', '').split('?')[0].trim();
      if (mail) emailSet.add(mail);
    });
    const foundEmails = htmlContent.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g);
    if (foundEmails) {
      foundEmails.forEach(e => {
        if (!e.endsWith('.png') && !e.endsWith('.jpg') && !e.endsWith('.svg') && !e.endsWith('.webp')) {
          emailSet.add(e);
        }
      });
    }
    const emailsList = Array.from(emailSet);

    // 6. استخراج أرقام الهواتف (Phones)
    const phoneSet = new Set();
    $('a[href^="tel:"]').each((_, el) => {
      const phone = $(el).attr('href').replace('tel:', '').trim();
      if (phone) phoneSet.add(phone);
    });
    const foundPhones = bodyText.match(/(\+?\d{1,4}[\s.-]?)?\(?\d{2,5}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}/g);
    if (foundPhones) {
      foundPhones.forEach(p => {
        const clean = p.trim();
        if (clean.length >= 8 && clean.length <= 18) phoneSet.add(clean);
      });
    }
    const phonesList = Array.from(phoneSet).slice(0, 5);

    // 7. استخراج روابط التواصل الاجتماعي (Social Links)
    const socialPlatforms = ['facebook.com', 'twitter.com', 'x.com', 'instagram.com', 'linkedin.com', 'youtube.com', 'tiktok.com', 'pinterest.com'];
    const socialLinksSet = new Set();
    $('a[href]').each((_, el) => {
      const href = $(el).attr('href');
      if (href) {
        socialPlatforms.forEach(platform => {
          if (href.includes(platform)) socialLinksSet.add(href);
        });
      }
    });
    const socialList = Array.from(socialLinksSet);

    // 8. العنوان الجغرافي (Address)
    const address =
      $('meta[property="business:contact_data:street_address"]').attr('content') ||
      $('address').text().trim() ||
      'No address found.';

    return {
      name: title,
      title: title,
      description: description,
      address: address,
      url: targetUrl,
      og_image: og_image || favicon,
      favicon: favicon,
      logo: og_image || favicon || 'No logo found.',
      keywords: keywords,
      social_links: socialList,
      phone: phonesList.length > 0 ? phonesList[0] : 'No phone found.',
      email: emailsList.length > 0 ? emailsList[0] : 'No email found.',
      phones: phonesList,
      emails: emailsList,
      pages_scraped: []
    };
  } catch (error) {
    throw new Error('Failed to scrape website: ' + error.message);
  }
};

module.exports = {
  runPythonScraper
};