const REPORT_BASE_URL = 'https://mint-scraper.fly.dev';

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Mint Tools')
    .addItem('Open Job Sidebar', 'showMintSidebar')
    .addToUi();
}

function showMintSidebar() {
  const html = HtmlService.createHtmlOutputFromFile('Sidebar')
    .setTitle('Mint Jobs');
  SpreadsheetApp.getUi().showSidebar(html);
}

function getReportToken_() {
  const token = PropertiesService.getScriptProperties().getProperty('REPORT_TOKEN');
  if (!token) {
    throw new Error('Missing REPORT_TOKEN script property');
  }
  return token;
}

function startJob(jobType) {
  const token = getReportToken_();
  const endpoint = jobType === 'scrape' ? '/scrape' : '/generate';
  const url = REPORT_BASE_URL + endpoint + '?token=' + encodeURIComponent(token);

  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    muteHttpExceptions: true,
  });

  const body = response.getContentText();
  let payload;
  try {
    payload = JSON.parse(body);
  } catch (err) {
    payload = { raw: body };
  }

  return {
    ok: response.getResponseCode() >= 200 && response.getResponseCode() < 300,
    code: response.getResponseCode(),
    payload: payload,
    jobType: jobType,
  };
}

function getJobStatus(jobType) {
  const token = getReportToken_();
  const endpoint = jobType === 'scrape' ? '/scrape/status' : '/generate/status';
  const url = REPORT_BASE_URL + endpoint + '?token=' + encodeURIComponent(token);

  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
  });

  const body = response.getContentText();
  let payload;
  try {
    payload = JSON.parse(body);
  } catch (err) {
    payload = { raw: body };
  }

  return {
    ok: response.getResponseCode() >= 200 && response.getResponseCode() < 300,
    code: response.getResponseCode(),
    payload: payload,
    jobType: jobType,
  };
}
