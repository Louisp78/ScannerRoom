<script setup lang="ts">
// Legal notice, terms of use and privacy policy (French LCEN and GDPR), one page
// with an anchor per section. Keep the privacy section in line with what the API
// actually stores (api/src/db/schema.ts) whenever the data model changes.
const CONTACT_EMAIL = 'lgup.official@gmail.com'
const LAST_UPDATED = '11 November 2026'

const sections = [
  { id: 'notice', title: 'Legal notice' },
  { id: 'terms', title: 'Terms of use' },
  { id: 'privacy', title: 'Privacy policy' },
]
</script>

<template>
  <div class="relative isolate min-h-svh px-4 py-6 sm:py-10">
    <div
      class="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_50%_0%,rgb(44_211_217/0.12),transparent_60%)]"
      aria-hidden="true"
    />
    <header class="mx-auto flex max-w-3xl items-center justify-between gap-3">
      <RouterLink
        to="/"
        class="inline-flex items-center gap-2 font-semibold tracking-wide text-scanner focus-visible:outline-2 focus-visible:outline-scanner"
      >
        <span class="size-2.5 rounded-full bg-scanner shadow-[0_0_8px_var(--color-scanner)]" />
        ScannerRoom
      </RouterLink>
    </header>

    <main class="legal mx-auto mt-10 max-w-3xl pb-16 text-foam/80">
      <h1 class="text-3xl font-semibold text-foam">Legal information</h1>
      <p class="mt-2 text-sm text-foam/50">Last updated: {{ LAST_UPDATED }}</p>
      <nav aria-label="Sections" class="mt-6 flex flex-wrap gap-2 text-sm">
        <a
          v-for="s in sections"
          :key="s.id"
          :href="`#${s.id}`"
          class="rounded-full border border-scanner/40 px-3 py-1 text-scanner hover:bg-scanner/10"
        >
          {{ s.title }}
        </a>
      </nav>

      <section id="notice">
        <h2>Legal notice</h2>
        <p>
          ScannerRoom (scannerroom.louisplace.com) is a non-commercial project published by
          <strong>Louis Place</strong>, an individual, who is also the director of publication.
          Contact: <a :href="`mailto:${CONTACT_EMAIL}`">{{ CONTACT_EMAIL }}</a
          >.
        </p>
        <p>
          Hosting: <strong>OVH SAS</strong>, 2 rue Kellermann, 59100 Roubaix, France, +33 9 72 10 10
          07. Content delivery and protection: Cloudflare, Inc., 101 Townsend Street, San Francisco,
          CA 94107, USA.
        </p>
      </section>

      <section id="terms">
        <h2>Terms of use</h2>
        <h3>The service</h3>
        <p>
          ScannerRoom is a free atlas of 3D seabed reconstructions built from underwater transect
          videos. The atlas and the transects are reserved to signed-in members; a few showcase
          transects, such as the one on the home page, are open to everyone. Signing in means you
          accept these terms.
        </p>
        <h3>Your account</h3>
        <p>
          You sign in with your ORCID or Google account; ScannerRoom never sees your password. An
          account is personal: do not share it. You can ask for your account to be deleted at any
          time (see <a href="#privacy">Privacy policy</a>).
        </p>
        <h3>Acceptable use</h3>
        <p>
          Do not try to bypass access restrictions, overload the service, or bulk-download the data.
          Transects are shared with members for viewing and research: do not republish them without
          the contributor's permission. Accounts that break these rules may be suspended.
        </p>
        <h3>Contributions</h3>
        <p>
          When you contribute a transect, you confirm that you have the rights to the footage and
          the permissions needed to film where you did. You keep every right to your content and
          give ScannerRoom a free, non-exclusive licence to store it, reconstruct it and show it to
          members (and to everyone if it is made a showcase transect, with your agreement), for as
          long as it stays online. Your name and ORCID iD are shown as its contributor. You can ask
          for a contribution to be removed at any time.
        </p>
        <h3>Liability</h3>
        <p>
          Reconstructions are provided as they are, without any guarantee of accuracy: they must not
          be used for navigation or safety decisions. The service is free and may be interrupted or
          changed at any time.
        </p>
        <h3>Changes and applicable law</h3>
        <p>
          These terms may change; the date at the top of this page shows the latest version. They
          are governed by French law.
        </p>
      </section>

      <section id="privacy">
        <h2>Privacy policy</h2>
        <p>
          The data controller is Louis Place (contact:
          <a :href="`mailto:${CONTACT_EMAIL}`">{{ CONTACT_EMAIL }}</a
          >). ScannerRoom collects as little as it can, never sells data, and uses no advertising or
          analytics.
        </p>
        <h3>What is collected, why and for how long</h3>
        <ul>
          <li>
            <strong>Your account</strong>: the identifier the sign-in provider gives your account,
            the name it shares, and your ORCID iD if you sign in with ORCID. Your email address is
            not collected. Used to run your account and to credit your transects (performance of
            these terms). Kept until you ask for the account to be deleted.
          </li>
          <li>
            <strong>Session cookie</strong> (<code>sr.sid</code>): keeps you signed in. It is
            strictly necessary, so it needs no consent; it expires 30 days after sign-in or when you
            sign out. Cloudflare may also set a security cookie (such as <code>__cf_bm</code>) to
            filter bots, equally exempt from consent. No analytics, advertising or tracking cookie
            is used, which is why there is no cookie banner.
          </li>
          <li>
            <strong>Contributions</strong>: the transects credited to you and their attribution
            (your name and ORCID iD), visible to signed-in members, and to everyone for showcase
            transects. Kept while the transect is online.
          </li>
          <li>
            <strong>Technical logs</strong>: IP address, requested page, date and browser, recorded
            by the servers and by Cloudflare to keep the service secure and working (legitimate
            interest). Kept no longer than 12 months.
          </li>
          <li>
            <strong>Access requests</strong>: the request form opens your own email app; the email
            you send is kept only as long as needed to answer it.
          </li>
        </ul>
        <h3>Who receives it</h3>
        <p>
          Administrators see the list of members (names and ORCID iDs) to assign transects. The data
          is hosted by OVHcloud in the European Union. Cloudflare, which carries the traffic, may
          process technical data in the United States under the EU–US Data Privacy Framework.
          Signing in with ORCID or Google is also governed by that provider's own privacy policy.
        </p>
        <h3>Your rights</h3>
        <p>
          Under the GDPR you can access, correct, delete or export your data, and object to or
          restrict its use. Write to
          <a :href="`mailto:${CONTACT_EMAIL}`">{{ CONTACT_EMAIL }}</a> from the account's email or
          while signed in; you will get an answer within one month. You can also file a complaint
          with the CNIL (<a href="https://www.cnil.fr" target="_blank" rel="noopener">www.cnil.fr</a
          >).
        </p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.legal section {
  margin-top: 3rem;
  scroll-margin-top: 1.5rem;
}
.legal h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--color-foam);
}
.legal h3 {
  margin-top: 1.5rem;
  font-weight: 600;
  color: var(--color-foam);
}
.legal p,
.legal ul {
  margin-top: 0.75rem;
  line-height: 1.7;
}
.legal ul {
  list-style: disc;
  padding-left: 1.25rem;
}
.legal li + li {
  margin-top: 0.5rem;
}
.legal a {
  color: var(--color-scanner);
}
.legal a:hover {
  text-decoration: underline;
}
</style>
