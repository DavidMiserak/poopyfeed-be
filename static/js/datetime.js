/**
 * Shared Day.js datetime utilities for timezone conversion and display.
 */
var DateTimeUtils = (function() {
  'use strict';

  /**
   * Initialize a datetime-local form input with timezone handling.
   * - Sets the hidden tz_offset field to the browser's timezone offset
   * - Converts existing UTC values to local time for display
   * - Defaults new entries to current local time
   */
  function initFormDatetime() {
    var tzOffset = new Date().getTimezoneOffset();
    var tzInput = document.querySelector('.tz-offset');
    if (tzInput) {
      tzInput.value = tzOffset;
    }

    var dtInput = document.querySelector('.local-datetime');
    if (dtInput) {
      if (dtInput.value) {
        // Editing: convert UTC value to local time for display
        var utcDate = dayjs(dtInput.value);
        var localDate = utcDate.subtract(tzOffset, 'minute');
        dtInput.value = localDate.format('YYYY-MM-DDTHH:mm');
      } else {
        // Creating: default to current local time
        dtInput.value = dayjs().format('YYYY-MM-DDTHH:mm');
      }
    }
  }

  /**
   * Format all elements with class 'local-time-relative' as relative time.
   * Elements should have a data-datetime attribute with an ISO 8601 datetime.
   */
  function formatRelativeTimes() {
    document.querySelectorAll('.local-time-relative').forEach(function(el) {
      var date = dayjs(el.getAttribute('data-datetime'));
      el.textContent = date.fromNow();
    });
  }

  /**
   * Format all elements with class 'local-time-exact' as formatted local time.
   * Elements should have a data-datetime attribute with an ISO 8601 datetime.
   */
  function formatExactTimes() {
    document.querySelectorAll('.local-time-exact').forEach(function(el) {
      var date = dayjs(el.getAttribute('data-datetime'));
      el.textContent = date.format('MMM D, h:mm A');
    });
  }

  /**
   * Format all elements with class 'relative-time' as relative time.
   * Elements should have a datetime attribute with an ISO 8601 datetime.
   */
  function formatRelativeTimeElements() {
    document.querySelectorAll('.relative-time').forEach(function(el) {
      var date = dayjs(el.getAttribute('datetime'));
      el.textContent = date.fromNow();
    });
  }

  /**
   * Format all elements with class 'child-age' to show age.
   * Elements should have a data-dob attribute with an ISO 8601 date.
   */
  function formatChildAges() {
    document.querySelectorAll('.child-age').forEach(function(el) {
      var dob = dayjs(el.getAttribute('data-dob'));
      var age = dayjs().to(dob, true);
      el.textContent = '(' + age + ' old)';
    });
  }

  return {
    initFormDatetime: initFormDatetime,
    formatRelativeTimes: formatRelativeTimes,
    formatExactTimes: formatExactTimes,
    formatRelativeTimeElements: formatRelativeTimeElements,
    formatChildAges: formatChildAges
  };
})();
