import React from 'react';
import { useRouteError, Link } from 'react-router-dom';
import { Container, Alert, Button } from 'react-bootstrap';

/**
 * ErrorPage ist eine generische Fehlerseite, die angezeigt wird,
 * wenn ein Loader oder eine Action in einer Route einen Fehler wirft.
 * Sie gehört zum "app"-Feature, da sie eine globale Funktion darstellt.
 */
export default function ErrorPage() {
    const error = useRouteError();
    console.error("Ein Fehler wurde vom Router gefangen:", error);

    let errorTitle = "Ein unerwarteter Fehler ist aufgetreten.";
    let errorMessage = "Bitte versuchen Sie, die Seite neu zu laden oder kehren Sie zur Startseite zurück.";

    if (error.status === 404) {
        errorTitle = "Seite nicht gefunden (404)";
        errorMessage = "Die von Ihnen angeforderte Ressource konnte nicht gefunden werden.";
    } else if (error.statusText) {
        errorTitle = `Fehler: ${error.statusText}`;
        errorMessage = error.data?.message || "Beim Laden der Daten ist ein Problem aufgetreten.";
    }

    return (
        <Container className="d-flex align-items-center justify-content-center" style={{ minHeight: '100vh' }}>
            <Alert variant="danger" className="text-center">
                <Alert.Heading>{errorTitle}</Alert.Heading>
                <p>{errorMessage}</p>
                <hr />
                <div className="d-flex justify-content-center">
                    <Button as={Link} to="/" variant="outline-danger">
                        Zurück zur Startseite
                    </Button>
                </div>
            </Alert>
        </Container>
    );
}