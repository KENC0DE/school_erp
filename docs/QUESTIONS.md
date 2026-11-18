# Open questions

Written here when truly blocked; work continues on another task meanwhile.

1. **Payment provider credentials and regulatory status** (Phase 7): Chapa, ArifPay,
   SantimPay, telebirr and CBE Birr sandbox access must be supplied by the owner
   before adapters can be enabled. Until then they are disabled stubs with fixtures.
2. **SMS provider** (Phase 1/8): provider and credentials not chosen. Adapter stub in
   place.
3. **Ethiopian curriculum starter data** (Phase 2): shipped as *unverified starter
   data*; needs review against the official curriculum by the school.
4. **Tax and pension rates** (Phase 3/7): configuration only, marked "to be validated
   by an accountant".
5. **Amharic translation review** (Phase 14): drafted strings need a human reviewer.
6. **Legal review** (Phase 14): privacy notice, data retention and data-subject
   workflows need a local lawyer.
7. **Push credentials** (Phase 11): Expo/FCM/APNs project credentials are required for
   real delivery; a logging fake provider is used until then.
8. **App store accounts** (Phase 12): Apple Developer and Google Play accounts are
   required for EAS production builds.
9. **P3 owner script on a physical phone** (Phase 3): the offline outbox is covered
   by Jest, and attendance scope isolation is covered by API tests, but the owner
   script still needs a human with Expo Go and a real network toggle to mark a
   register in airplane mode and reconnect. Not possible on this host.
