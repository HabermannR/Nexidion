// src/components/Contact.jsx
import React from 'react';
import styles from './Menu.module.css';

function Contact() {
  return (
  <div className={styles.MenuWrapper}>
    <div className={styles.MenuContainer}>
      <h2 className={styles.MenuTitle}>Contact</h2>
      <div className={styles.ContactInfo}>
        <p>
          <strong>Email:</strong>{' '}
          <a href="mailto:Richardhabermann1@gmail.com">Richardhabermann1@gmail.com</a>
        </p>
        <p>
          <strong>Phone:</strong>{' '}
          <a href="tel:+4901765239723">+49 0176 52 39 72 39</a>
        </p>
      </div>
      <div className={styles.SocialMedia}>
        <h3>Follow me</h3>
        <ul>
          <li>
            <a
              href="https://www.linkedin.com/in/richard-habermann-3437191b5/"
              target="_blank"
              rel="noopener noreferrer"
            >
              LinkedIn
            </a>
          </li>
        </ul>
      </div>
    </div>
   </div>
  );
}

export default Contact;