import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, Typography, Card, CardContent, Grid } from '@mui/material';
import { AbstractSection, SectionProps } from './common';


interface OverviewDataRow {
    ticker: string;
    last_price: number;
    volume: number;
    value: number;
    fee: number;
    invested: number;
    profit: number;
}

interface OverviewState {
    investment: number;
    fees: number;
    value: number;
    profit: number;
    overview: Array<OverviewDataRow>;
}

interface OverviewProps {}

export class Overview extends AbstractSection<OverviewProps, OverviewState> {

    sectionName = () => 'Overview';

    constructor(props: OverviewProps & SectionProps) {
        super(props);
        this.state = {
            investment: 0,
            fees: 0,
            value: 0,
            profit: 0,
            overview: [],
        };

        this.loadOverview = this.loadOverview.bind(this);
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadOverview().then(() =>
            this.props.displayProgressBar(false)
        );
    }

    loadOverview() {
        const params = new URLSearchParams();
        // params.append('ticker', 'CEZ.PR');
        return fetch(`/overview/get?${params.toString()}`)
            .then<Array<OverviewDataRow>>(res => res.json())
            .then(overview => this.setState({
                overview,
                investment: overview.reduce((prev, cur, i) => prev + cur.invested, 0),
                fees: overview.reduce((prev, cur, i) => prev + cur.fee, 0),
                value: overview.reduce((prev, cur, i) => prev + cur.value, 0),
                profit: overview.reduce((prev, cur, i) => prev + cur.profit, 0),
            }));
    }

    render() {

        return <Box>
            <Box>
                <Grid container spacing={2}>
                    <Grid item xs={3}>
                        <Card elevation={3}>
                            <CardContent>
                                <Typography variant="h5" component="div">Investment</Typography>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">{this.state.investment.toFixed()}</Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={3}>
                        <Card elevation={3}>
                            <CardContent>
                                <Typography variant="h5" component="div">Fees</Typography>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">{this.state.fees.toFixed(2)}</Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={3}>
                        <Card elevation={3}>
                            <CardContent>
                                <Typography variant="h5" component="div">Value</Typography>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">{this.state.value.toFixed()}</Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={3}>
                        <Card elevation={3}>
                            <CardContent>
                                <Typography variant="h5" component="div">Profit</Typography>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">{this.state.profit.toFixed(2)} ({(100*this.state.profit/this.state.investment).toFixed(1)}%)</Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Ticker</TableCell>
                                <TableCell>Last price</TableCell>
                                <TableCell>Volume</TableCell>
                                <TableCell>Invested</TableCell>
                                <TableCell>Fee</TableCell>
                                <TableCell>Value</TableCell>
                                <TableCell>Profit</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {this.state.overview.map(
                                (item, i) => <TableRow key={i} sx={{backgroundColor: item.profit < 0 ? 'rgba(255,0,0,0.3)' : 'rgba(0,255,0,0.3)'}}>
                                    <TableCell>{item.ticker}</TableCell>
                                    <TableCell>{item.last_price ? item.last_price.toFixed(2) : null}</TableCell>
                                    <TableCell>{item.volume ? item.volume : null}</TableCell>
                                    <TableCell>{item.invested.toFixed()}</TableCell>
                                    <TableCell>{item.fee.toFixed(2)}</TableCell>
                                    <TableCell>{item.value.toFixed()}</TableCell>
                                    <TableCell>{item.profit.toFixed(2)} ({(100*item.profit/item.invested).toFixed(1)}%)</TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Box>
        </Box>
    }
}