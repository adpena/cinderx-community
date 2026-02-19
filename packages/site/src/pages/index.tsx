import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import clsx from 'clsx';

import styles from './index.module.css';

const cards = [
  {
    title: 'Docs',
    description:
      'Source-grounded guidance for setup, concepts, and community practices around CinderX.'
  },
  {
    title: 'Benchmarks',
    description:
      'CinderX-first benchmark dashboards and reproducible methodology for runtime comparisons.'
  },
  {
    title: 'Compatibility Guidance',
    description:
      'Careful, explicit compatibility notes across platforms and C-extension expectations.'
  },
  {
    title: 'Real-World Case Studies',
    description: 'A home for practical workload reports as transparent community research evolves.'
  }
];

export default function Home() {
  return (
    <Layout>
      <main className={styles.page}>
        <div className="container">
          <section className={clsx(styles.hero, 'hero-shadow')}>
            <p className={styles.heroKicker}>Community Documentation and Tooling</p>
            <h1 className={styles.heroTitle}>CinderX Community</h1>
            <p className={styles.heroTagline}>
              CinderX-focused documentation and benchmarking that compares runtimes against a
              CinderX baseline with transparent, reproducible metadata.
            </p>
            <div className={styles.heroButtons}>
              <Link className="button button--primary button--lg" to="/docs/install">
                Installation
              </Link>
              <Link
                className="button button--secondary button--lg"
                to="/docs/tutorials/django-dummy-service"
              >
                Hands-on Tutorial
              </Link>
              <Link
                className="button button--secondary button--lg"
                to="/docs/benchmarks/results-placeholder"
              >
                CinderX Results Dashboard
              </Link>
            </div>
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>What you'll find here</h2>
            <div className={clsx('card-grid', styles.cards)}>
              {cards.map((card) => (
                <article key={card.title} className={styles.card}>
                  <h3>{card.title}</h3>
                  <p>{card.description}</p>
                </article>
              ))}
            </div>
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Status</h2>
            <div className={styles.callout}>
              <p>
                CinderX is described in its upstream README as experimental for external users,
                production-tested at Meta, and released weekly on PyPI.
              </p>
              <p>
                External compatibility remains version- and platform-dependent; this site tracks
                source-backed guidance only.
              </p>
            </div>
            <p className={styles.references}>
              Sources:{' '}
              <Link href="https://github.com/facebookincubator/cinderx">CinderX README</Link>
            </p>
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Benchmarks done right</h2>
            <p>
              We follow pyperformance principles while centering CinderX as the primary comparison
              baseline: stable measurements, repeatability, and explicit runtime metadata.
            </p>
            <p>
              The benchmark dashboard highlights how other runtimes perform relative to CinderX for
              the same workload set.
            </p>
            <p className={styles.references}>
              Source:{' '}
              <Link href="https://pyperformance.readthedocs.io/usage.html">pyperformance docs</Link>
            </p>
          </section>
        </div>
      </main>
    </Layout>
  );
}
