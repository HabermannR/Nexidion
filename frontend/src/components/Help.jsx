// src/components/Help.jsx
import React from 'react';
import styles from './Menu.module.css';

function Help() {
  return (
    <div className={styles.MenuWrapper}>
		<div className={styles.MenuContainer}>
		  <h2 className={styles.MenuTitle}>CorteXtract Help</h2>
		  <div className={styles.MenuForm}>
			<h3>Welcome to CorteXtract</h3>
			<p>Your intelligent knowledge management system. This guide will help you navigate and use the main features of the application.</p>
			<p>Please be advised that the server is running on a local PC, and all data is stored in plain text in a sqlite database. Please do not enter confidential information!</p>

			<section>
			  <h3>Vault Selection</h3>
			  <ul className={styles.MenuList}>
				<li>Use the "Vault" dropdown in the top bar to switch between different vaults.</li>
				<li>Changing the vault will update the tree view and content area accordingly.</li>
			  </ul>
			</section>

			<section>
			  <h3>LLM Model Selection</h3>
			  <p>Use the "LLM" dropdown to choose the AI model for content generation and enhancement:</p>
			  <ul className={styles.MenuList}>
				<li>Claude 3.5 Sonnet</li>
				<li>GPT-3.5 Turbo</li>
				<li>GPT-4o</li>
				<li>Local (if available)</li>
			  </ul>
			</section>
			
			<section>
			  <h3>Navigation</h3>
			  <p>The top bar contains links to different sections of the application:</p>
			  <ul className={styles.MenuList}>
				<li>Chat: Opens the chat interface to interact with your vault.</li>
				<li>Contact: Provides contact information for support.</li>
				<li>Help: Opens this help page.</li>
				<li>Settings: Allows you to manage your account settings. Here you can change your Password, create new Vaults and invite other users to see or work in your vaults!</li>
				<li>Admin: (Only visible to admin users) Provides access to administrative functions.</li>
			  </ul>
			</section>

			

			<section>
			  <h3>Node Management</h3>
			  <ul className={styles.MenuList}>
				<li>The left sidebar displays your vault's tree structure.</li>
				<li>Click on a node to view its content.</li>
				<li>To add a new node:
				  <ol>
					<li>Click the "+" button next to a parent node.</li>
					<li>Enter the new node's title in the input field.</li>
					<li>Click "Add" to create the node or "Cancel" to abort.</li>
				  </ol>
				</li>
				<li>To delete a node, click the "-" button next to it and confirm the deletion.</li>
				<li>You can drag and drop nodes to reorganize the tree structure.</li>
			  </ul>
			</section>

			<section>
			  <h3>Content Editing</h3>
			  <ul className={styles.MenuList}>
				<li>Click the "Edit" button to modify the content of a node.</li>
				<li>Use the text area to make your changes.</li>
				<li>Click "Save" to update the content or "Cancel" to discard changes.</li>
			  </ul>
			</section>

			<section>
			  <h3>Version History</h3>
			  <ul className={styles.MenuList}>
				<li>The version history is displayed below the content area.</li>
				<li>Click on a version to view its content.</li>
				<li>Use the "Back to Current" button to return to the latest version.</li>
			  </ul>
			</section>

			<section>
			  <h3>AI-Assisted Features</h3>
			  <ul className={styles.MenuList}>
				<li>Create Content: Automatically generates content for the current node using the selected LLM model.</li>
				<li>Enhance Content: Improves and expands the existing content using AI assistance.</li>
			  </ul>
			</section>

			<section>
			  <h3>Tree Structure Optimization</h3>
			  <ul className={styles.MenuList}>
				<li>Click the "Optimize Structure" button to receive AI-generated suggestions for improving your vault's organization.</li>
				<li>Review the suggested structure in the modal window that appears.</li>
			  </ul>
			</section>

			<p>Remember to save your changes regularly and use the AI-assisted features to enhance your knowledge management experience. If you need further assistance, please use the Contact link.</p>
		  </div>
		</div>
    </div>
  );
}

export default Help;