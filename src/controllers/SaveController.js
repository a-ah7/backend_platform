const pool = require("../config/database");

function getFirstValue(singleValue, arrayValue) {
  if (
    typeof singleValue === "string" &&
    singleValue.trim() !== ""
  ) {
    return singleValue.trim();
  }

  if (Array.isArray(arrayValue) && arrayValue.length > 0) {
    const firstValue = arrayValue.find(
      (value) =>
        typeof value === "string" &&
        value.trim() !== ""
    );

    return firstValue ? firstValue.trim() : null;
  }

  return null;
}

async function saveScrapedData(request, response) {
  /*
   * يدعم طريقتين من الـFrontend:
   *
   * 1- { data: scrapedData }
   * 2- إرسال scrapedData مباشرة
   */
  const scrapedData =
    request.body &&
    request.body.data &&
    typeof request.body.data === "object"
      ? request.body.data
      : request.body;

  if (
    !scrapedData ||
    typeof scrapedData !== "object"
  ) {
    return response.status(400).json({
      success: false,
      message: "Scraped data is required",
    });
  }

  if (
    typeof scrapedData.url !== "string" ||
    scrapedData.url.trim() === ""
  ) {
    return response.status(400).json({
      success: false,
      message: "URL is required",
    });
  }

  let normalizedUrl;

  try {
    const parsedUrl = new URL(
      scrapedData.url.trim()
    );

    if (
      parsedUrl.protocol !== "http:" &&
      parsedUrl.protocol !== "https:"
    ) {
      return response.status(400).json({
        success: false,
        message:
          "Only HTTP and HTTPS URLs are allowed",
      });
    }

    normalizedUrl = parsedUrl.toString();
  } catch (error) {
    return response.status(400).json({
      success: false,
      message: "Invalid URL",
    });
  }

  let requestId = null;
  let dataId = null;

  try {
    /*
     * تحويل keywords وsocial_links إلى JSON
     * حتى تنخزن داخل قاعدة البيانات.
     */
    const keywordsJson = JSON.stringify(
      Array.isArray(scrapedData.keywords)
        ? scrapedData.keywords
        : []
    );

    const socialLinksJson = JSON.stringify(
      Array.isArray(scrapedData.social_links)
        ? scrapedData.social_links
        : []
    );

    /*
     * استخراج أول رقم.
     * يدعم phone أو phones.
     */
    const phone = getFirstValue(
      scrapedData.phone,
      scrapedData.phones
    );

    /*
     * استخراج أول إيميل.
     * يدعم email أو emails.
     */
    const email = getFirstValue(
      scrapedData.email,
      scrapedData.emails
    );

    /*
     * أولًا: إنشاء Scraping Request.
     * هذا الأمر ما يشتغل إلا بعد ضغط زر Save.
     */
    const [requestResult] = await pool.execute(
      "INSERT INTO Scraping_Request (url) VALUES (?)",
      [normalizedUrl]
    );

    requestId = requestResult.insertId;

    /*
     * تغيير حالة الطلب إلى processing.
     */
    await pool.execute(
      "UPDATE Scraping_Request SET status = ? WHERE request_id = ?",
      ["processing", requestId]
    );

    /*
     * إنشاء سجل فارغ داخل Scraped_Data.
     */
    const [dataResult] = await pool.execute(
      "INSERT INTO Scraped_Data (request_id) VALUES (?)",
      [requestId]
    );

    dataId = dataResult.insertId;

    /*
     * تخزين العنوان.
     */
    await pool.execute(
      "UPDATE Scraped_Data SET title = ? WHERE id = ?",
      [
        scrapedData.title || null,
        dataId,
      ]
    );

    /*
     * تخزين الوصف.
     */
    await pool.execute(
      "UPDATE Scraped_Data SET description = ? WHERE id = ?",
      [
        scrapedData.description || null,
        dataId,
      ]
    );

    /*
     * تخزين العنوان البريدي.
     */
    await pool.execute(
      "UPDATE Scraped_Data SET address = ? WHERE id = ?",
      [
        scrapedData.address || null,
        dataId,
      ]
    );

    /*
     * تخزين رابط الموقع.
     */
    await pool.execute(
      "UPDATE Scraped_Data SET url = ? WHERE id = ?",
      [
        normalizedUrl,
        dataId,
      ]
    );

    /*
     * تخزين صورة Open Graph.
     */
    await pool.execute(
      "UPDATE Scraped_Data SET og_image = ? WHERE id = ?",
      [
        scrapedData.og_image || null,
        dataId,]
    );

    /*
     * تخزين الكلمات المفتاحية.
     */
    await pool.execute(
      "UPDATE Scraped_Data SET keywords = ? WHERE id = ?",
      [
        keywordsJson,
        dataId,
      ]
    );

    /*
     * تخزين favicon.
     */
    await pool.execute(
      "UPDATE Scraped_Data SET favicon = ? WHERE id = ?",
      [
        scrapedData.favicon || null,
        dataId,
      ]
    );

    /*
     * تخزين روابط التواصل الاجتماعي.
     */
    await pool.execute(
      "UPDATE Scraped_Data SET social_links = ? WHERE id = ?",
      [
        socialLinksJson,
        dataId,
      ]
    );

    /*
     * تخزين رقم الهاتف.
     */
    await pool.execute(
      "UPDATE Scraped_Data SET phone = ? WHERE id = ?",
      [
        phone,
        dataId,
      ]
    );

    /*
     * تخزين البريد الإلكتروني.
     */
    await pool.execute(
      "UPDATE Scraped_Data SET email = ? WHERE id = ?",
      [
        email,
        dataId,
      ]
    );

    /*
     * تغيير حالة الطلب إلى completed.
     */
    await pool.execute(
      "UPDATE Scraping_Request SET status = ? WHERE request_id = ?",
      ["completed", requestId]
    );

    return response.status(201).json({
      success: true,
      message: "Data saved successfully",
      requestId,
      dataId,

      data: {
        title: scrapedData.title || "",
        description:
          scrapedData.description || "",
        address: scrapedData.address || "",
        url: normalizedUrl,
        og_image: scrapedData.og_image || "",

        keywords: Array.isArray(
          scrapedData.keywords
        )
          ? scrapedData.keywords
          : [],

        favicon: scrapedData.favicon || "",

        social_links: Array.isArray(
          scrapedData.social_links
        )
          ? scrapedData.social_links
          : [],

        phone: phone || "",
        email: email || "",
      },
    });
  } catch (error) {
    /*
     * إذا صار خطأ بعد إنشاء الطلب،
     * نغيّر حالته إلى failed.
     */
    if (requestId !== null) {
      try {
        await pool.execute(
          "UPDATE Scraping_Request SET status = ? WHERE request_id = ?",
          ["failed", requestId]
        );
      } catch (statusError) {
        console.error(
          "Failed to update request status:",
          statusError.message
        );
      }
    }

    console.error(
      "Saving failed:",
      error.message
    );

    return response.status(500).json({
      success: false,
      message: "Saving failed",
      error: error.message,
    });
  }
}

module.exports = {
  saveScrapedData,
};