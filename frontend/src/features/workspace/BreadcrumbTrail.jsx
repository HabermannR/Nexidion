import { Fragment } from 'react';
import { Breadcrumb, Dropdown } from 'react-bootstrap';
import { Link } from 'react-router-dom';

export default function BreadcrumbTrail({ path }) {
    if (!path?.length) return null;
    const hidden = path.length > 3 ? path.slice(1, -2) : [];
    const visible = hidden.length ? [path[0], ...path.slice(-2)] : path;

    return (
        <Breadcrumb listProps={{ className: 'mb-0 bg-transparent p-0 small' }}>
            {visible.map((crumb, index) => (
                <Fragment key={crumb.id}>
                    {index === 1 && hidden.length > 0 && (
                        <li className="breadcrumb-item breadcrumb-overflow">
                            <Dropdown>
                                <Dropdown.Toggle
                                    variant="link"
                                    size="sm"
                                    className="p-0 breadcrumb-ellipsis"
                                    aria-label="Show hidden ancestors"
                                    title="Show hidden ancestors"
                                >…</Dropdown.Toggle>
                                <Dropdown.Menu>
                                    {hidden.map(ancestor => (
                                        <Dropdown.Item as={Link} to={ancestor.to} key={ancestor.id} title={ancestor.title}>
                                            {ancestor.title}
                                        </Dropdown.Item>
                                    ))}
                                </Dropdown.Menu>
                            </Dropdown>
                        </li>
                    )}
                    <Breadcrumb.Item
                        linkAs={Link}
                        linkProps={{ to: crumb.to, title: crumb.title }}
                        active={index === visible.length - 1}
                        title={crumb.title}
                    >
                        <span className="breadcrumb-label">{crumb.title}</span>
                    </Breadcrumb.Item>
                </Fragment>
            ))}
        </Breadcrumb>
    );
}
